"""Cliente e Decodificador DSR para as APIs Públicas Power BI do InfoSaúde-DF (SPEC-06).

Consome diretamente:
1. PUB_ESTOQUE_ALTO_CUSTO (ResourceKey: a665320c-1f2b-43cd-8380-6d39f535daf9)
   - Tabela `estoque_geral_ceaf` (857 registros / 294 medicamentos nas 3 unidades do CEAF-DF)
   - Tabelas `Localização Asa Sul`, `Localização Ceilândia`, `Localização Gama` (Mapas Google Maps)
   - Tabela `Data_atualização` (Timestamp de atualização diária do painel)
2. PUB_DOC_MEDICAMENTOS (ResourceKey: d77b9ba0-317a-4041-88a0-3241c35384ac)
   - Tabela `Estabelecimentos` (228 unidades / 171 com latitude e longitude exatas no DF)
3. PUB_ESTOQUE_UBS (ResourceKey: 5ccba871-5230-4333-86f6-7fc3a29b5d5b)
"""

from __future__ import annotations

import json
import math
import re
import urllib.request
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sus_cidadao_ds.contracts.schemas import compute_sha256
from sus_cidadao_ds.retrieval.retrievers import normalize_pt_text

POWERBI_QUERY_ENDPOINT = (
    "https://wabi-brazil-south-api.analysis.windows.net/public/reports/querydata?synchronous=true"
)

CEAF_RESOURCE_KEY = "a665320c-1f2b-43cd-8380-6d39f535daf9"
CEAF_MODEL_ID = 10730466
CEAF_DATASET_ID = "424ade14-3f72-4830-a4dc-ab612ad877ee"

DOC_MAPS_RESOURCE_KEY = "d77b9ba0-317a-4041-88a0-3241c35384ac"
DOC_MAPS_MODEL_ID = 10722913
DOC_MAPS_DATASET_ID = "c021e607-7580-407e-bbab-4312c5c14cd9"

UBS_STOCK_RESOURCE_KEY = "5ccba871-5230-4333-86f6-7fc3a29b5d5b"
UBS_STOCK_MODEL_ID = 10723062
UBS_STOCK_DATASET_ID = "ceb0186a-2546-4bfd-814e-5dad49b318cc"


@dataclass(frozen=True)
class CEAFLiveStockItem:
    """Registro individual de estoque de medicamento nas Farmácias de Alto Custo (CEAF-DF)."""

    cod_produto: str
    desc_produto: str
    unidade: str  # "Asa Sul", "Ceilândia", "Gama"
    disp_estoque: str  # "COM ESTOQUE", "SEM ESTOQUE", "PROGRAMADO - COM ESTOQUE", etc.
    origem_abastecimento: str  # "SES-DF" ou "Ministério da Saúde"
    psicotropico: str
    ultima_atualizacao: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GeolocatedPharmacy:
    """Unidade de saúde / farmácia geolocalizada do Distrito Federal."""

    cnes: str
    name: str
    address: str
    neighborhood_or_ra: str
    pharmacy_type: str
    latitude: float | None
    longitude: float | None
    google_maps_url: str
    google_maps_embed: str = ""
    contact_email: str = ""
    covered_ras: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class InfoSaudeSyncSummary:
    """Resumo auditável da sincronização com o InfoSaúde-DF."""

    synced_at_utc: str
    ceaf_panel_updated_at_utc: str
    stock_update_schedule: str
    catalog_update_schedule: str
    total_ceaf_stock_rows: int
    distinct_ceaf_medications: int
    stock_by_status: dict[str, int]
    stock_by_unit: dict[str, dict[str, int]]
    total_establishments: int
    geolocated_establishments: int
    ceaf_units_with_maps: int
    stock_sha256: str
    maps_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def decode_powerbi_dsr(ds_block: dict[str, Any]) -> list[list[Any]]:
    """Descomprime o formato DSR (Data Shape Result) do Power BI aplicando máscaras R e Ø."""
    ph_list = ds_block.get("PH", [])
    if not ph_list or "DM0" not in ph_list[0]:
        return []
    dm0 = ph_list[0]["DM0"]
    if not dm0:
        return []

    vdicts: dict[str, list[Any]] = ds_block.get("ValueDicts", {})
    schema = dm0[0].get("S", [])
    col_dicts = [col_spec.get("DN") for col_spec in schema]
    n_cols = len(schema)

    prev_row: list[Any] = [None] * n_cols
    decoded_rows: list[list[Any]] = []

    for item in dm0:
        c_vals = item.get("C", [])
        r_mask = int(item.get("R", 0))
        null_mask = int(item.get("Ø", 0))
        current_row: list[Any] = [None] * n_cols
        c_idx = 0

        for col_i in range(n_cols):
            if (r_mask >> col_i) & 1:
                current_row[col_i] = prev_row[col_i]
            elif (null_mask >> col_i) & 1:
                current_row[col_i] = None
            else:
                raw_val = c_vals[c_idx] if c_idx < len(c_vals) else None
                c_idx += 1
                dict_name = col_dicts[col_i]
                if (
                    dict_name
                    and raw_val is not None
                    and isinstance(raw_val, int)
                    and dict_name in vdicts
                    and 0 <= raw_val < len(vdicts[dict_name])
                ):
                    current_row[col_i] = vdicts[dict_name][raw_val]
                else:
                    current_row[col_i] = raw_val

        prev_row = current_row
        decoded_rows.append(current_row)

    return decoded_rows


def extract_coords_from_maps_iframe(iframe_html: str) -> tuple[float | None, float | None, str]:
    """Extrai latitude, longitude e URL do iframe Google Maps embutido no Power BI."""
    src_match = re.search(r"src=['\"]([^'\"]+)['\"]", iframe_html)
    embed_url = src_match.group(1) if src_match else ""
    lng_match = re.search(r"!2d(-?\d+\.\d+)", embed_url)
    lat_match = re.search(r"!3d(-?\d+\.\d+)", embed_url)
    lat = float(lat_match.group(1)) if lat_match else None
    lng = float(lng_match.group(1)) if lng_match else None
    return lat, lng, embed_url


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula a distância geodésica Haversine em quilômetros entre dois pontos."""
    r_earth = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
    )
    return 2.0 * r_earth * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


class InfoSaudeLiveClient:
    """Cliente de ingestão das APIs Power BI do InfoSaúde-DF (Estoque CEAF + Mapas UBS/CEAF)."""

    def __init__(self, gold_dir: Path) -> None:
        self.gold_dir = gold_dir
        self.gold_dir.mkdir(parents=True, exist_ok=True)
        self.stock_path = self.gold_dir / "ceaf_live_stock.json"
        self.maps_path = self.gold_dir / "df_pharmacies_geolocated.json"

    @staticmethod
    def build_ceaf_stock_query_payload() -> dict[str, Any]:
        """Monta o payload SemanticQueryDataShapeCommand para `estoque_geral_ceaf`."""
        return {
            "version": "1.0.0",
            "queries": [
                {
                    "Query": {
                        "Commands": [
                            {
                                "SemanticQueryDataShapeCommand": {
                                    "Query": {
                                        "Version": 2,
                                        "From": [
                                            {
                                                "Name": "e",
                                                "Entity": "estoque_geral_ceaf",
                                                "Type": 0,
                                            }
                                        ],
                                        "Select": [
                                            {
                                                "Column": {
                                                    "Expression": {
                                                        "SourceRef": {"Source": "e"}
                                                    },
                                                    "Property": "cod_produto2",
                                                },
                                                "Name": "e.cod_produto2",
                                            },
                                            {
                                                "Column": {
                                                    "Expression": {
                                                        "SourceRef": {"Source": "e"}
                                                    },
                                                    "Property": "desc_produto",
                                                },
                                                "Name": "e.desc_produto",
                                            },
                                            {
                                                "Column": {
                                                    "Expression": {
                                                        "SourceRef": {"Source": "e"}
                                                    },
                                                    "Property": "unidade",
                                                },
                                                "Name": "e.unidade",
                                            },
                                            {
                                                "Column": {
                                                    "Expression": {
                                                        "SourceRef": {"Source": "e"}
                                                    },
                                                    "Property": "disp_estoque",
                                                },
                                                "Name": "e.disp_estoque",
                                            },
                                            {
                                                "Column": {
                                                    "Expression": {
                                                        "SourceRef": {"Source": "e"}
                                                    },
                                                    "Property": "Origem do Abastecimento",
                                                },
                                                "Name": "e.origem",
                                            },
                                            {
                                                "Column": {
                                                    "Expression": {
                                                        "SourceRef": {"Source": "e"}
                                                    },
                                                    "Property": "Texto Info",
                                                },
                                                "Name": "e.texto_info",
                                            },
                                            {
                                                "Column": {
                                                    "Expression": {
                                                        "SourceRef": {"Source": "e"}
                                                    },
                                                    "Property": "psicotropico",
                                                },
                                                "Name": "e.psicotropico",
                                            },
                                            {
                                                "Column": {
                                                    "Expression": {
                                                        "SourceRef": {"Source": "e"}
                                                    },
                                                    "Property": "ultima_atualizacao",
                                                },
                                                "Name": "e.ultima_atualizacao",
                                            },
                                        ],
                                    },
                                    "Binding": {
                                        "Primary": {
                                            "Groupings": [
                                                {"Projections": [0, 1, 2, 3, 4, 5, 6, 7]}
                                            ]
                                        },
                                        "DataReduction": {
                                            "DataVolume": 6,
                                            "Primary": {"Window": {"Count": 30000}},
                                        },
                                        "Version": 1,
                                    },
                                    "ExecutionMetricsKind": 1,
                                }
                            }
                        ]
                    },
                    "QueryId": "query_stock_ceaf_clean",
                    "ApplicationContext": {"DatasetId": CEAF_DATASET_ID},
                }
            ],
            "cancelQueries": [],
            "modelId": CEAF_MODEL_ID,
        }

    def _post_powerbi_query(
        self, resource_key: str, payload: dict[str, Any], timeout: int = 20
    ) -> dict[str, Any]:
        """Executa requisição HTTP POST contra o endpoint público do Power BI."""
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            POWERBI_QUERY_ENDPOINT,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-PowerBI-ResourceKey": resource_key,
                "User-Agent": "SUSCidadao-DataScience/0.2.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw_json: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
            return raw_json

    def sync_from_snapshots_or_live(
        self,
        stock_snapshot: Path = Path("/tmp/pbi_res_stock_clean.json"),
        ceaf_maps_snapshot: Path = Path("/tmp/pbi_res_maps.json"),
        doc_maps_snapshot: Path = Path("/tmp/pbi_res_doc_maps.json"),
        prefer_live: bool = False,
    ) -> InfoSaudeSyncSummary:
        """Sincroniza estoque CEAF e mapas das farmácias do DF via API ou snapshot DSR."""
        if prefer_live or not stock_snapshot.exists():
            raw_stock = self._post_powerbi_query(
                CEAF_RESOURCE_KEY, self.build_ceaf_stock_query_payload()
            )
        else:
            raw_stock = json.loads(stock_snapshot.read_text(encoding="utf-8"))

        raw_ceaf_maps = (
            json.loads(ceaf_maps_snapshot.read_text(encoding="utf-8"))
            if ceaf_maps_snapshot.exists()
            else {}
        )
        raw_doc_maps = (
            json.loads(doc_maps_snapshot.read_text(encoding="utf-8"))
            if doc_maps_snapshot.exists()
            else {}
        )

        # 1. Decodifica estoque CEAF
        ds_stock = raw_stock["results"][0]["result"]["data"]["dsr"]["DS"][0]
        decoded_stock_rows = decode_powerbi_dsr(ds_stock)

        stock_items: list[CEAFLiveStockItem] = []
        last_seen_update = "05/11/2026 13:45:15"
        for row in decoded_stock_rows:
            if row[7]:
                last_seen_update = str(row[7])
            stock_items.append(
                CEAFLiveStockItem(
                    cod_produto=str(row[0] or ""),
                    desc_produto=str(row[1] or ""),
                    unidade=str(row[2] or ""),
                    disp_estoque=str(row[3] or "SEM INFORMAÇÃO"),
                    origem_abastecimento=str(row[4] or "SES-DF"),
                    psicotropico=str(row[6] or "Outros"),
                    ultima_atualizacao=str(row[7] or last_seen_update),
                )
            )

        # 2. Extrai timestamp de atualização do painel CEAF
        panel_updated_utc = datetime.now(UTC).isoformat()
        if raw_ceaf_maps.get("results"):
            try:
                ts_ms = raw_ceaf_maps["results"][0]["result"]["data"]["dsr"]["DS"][0][
                    "PH"
                ][0]["DM0"][0]["G0"]
                panel_updated_utc = datetime.fromtimestamp(
                    float(ts_ms) / 1000.0, tz=UTC
                ).isoformat()
            except (KeyError, IndexError, TypeError, ValueError):
                pass

        # 3. Decodifica as 3 Farmácias de Alto Custo (CEAF) com Mapas Google Maps
        ceaf_meta = {
            "Farmácia Asa Sul": {
                "cnes": "CEAF-ASA-SUL",
                "address": "Estação 102 Sul do Metrô - Subsolo, Asa Sul, Brasília - DF",
                "ra": "Plano Piloto (Asa Sul)",
                "email": "cadastroceafasasul@gmail.com",
                "ras": [
                    "Asa Norte",
                    "Asa Sul",
                    "Cruzeiro",
                    "Guará",
                    "Itapoã",
                    "Jardim Botânico",
                    "Lago Norte",
                    "Lago Sul",
                    "Noroeste",
                    "Núcleo Bandeirante",
                    "Paranoá",
                    "Planaltina",
                    "São Sebastião",
                    "Sobradinho",
                    "Sudoeste",
                    "Varjão",
                ],
            },
            "Farmácia de Ceilândia": {
                "cnes": "CEAF-CEILANDIA",
                "address": "EQNN 18/20 Bloco B, Praça do Cidadão, Ceilândia Sul - DF",
                "ra": "Ceilândia",
                "email": "ceafceilandia@gmail.com",
                "ras": [
                    "Águas Claras",
                    "Arniqueira",
                    "Brazlândia",
                    "Candangolândia",
                    "Ceilândia",
                    "Estrutural",
                    "Park Way",
                    "Recanto das Emas",
                    "Riacho Fundo I",
                    "Riacho Fundo II",
                    "Samambaia",
                    "Sol Nascente/Pôr do Sol",
                    "Taguatinga",
                    "Vicente Pires",
                ],
            },
            "Farmácia do Gama": {
                "cnes": "CEAF-GAMA",
                "address": "Praça 1, Setor Leste (ao lado da Rodoviária), Gama - DF",
                "ra": "Gama",
                "email": "cadastroaltocustogama@gmail.com",
                "ras": ["Gama", "Santa Maria"],
            },
        }

        pharmacies: list[GeolocatedPharmacy] = []
        ceaf_results = raw_ceaf_maps.get("results", [])[1:4]
        for res_item in ceaf_results:
            ds_map = res_item["result"]["data"]["dsr"]["DS"][0]
            map_rows = decode_powerbi_dsr(ds_map)
            if not map_rows:
                continue
            unit_name = str(map_rows[0][0])
            iframe_str = str(map_rows[0][1])
            lat, lng, embed_url = extract_coords_from_maps_iframe(iframe_str)
            meta = ceaf_meta.get(unit_name, {})
            direct_url = (
                f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
                if lat is not None and lng is not None
                else embed_url
            )
            pharmacies.append(
                GeolocatedPharmacy(
                    cnes=str(meta.get("cnes", "CEAF-DF")),
                    name=unit_name,
                    address=str(meta.get("address", unit_name)),
                    neighborhood_or_ra=str(meta.get("ra", unit_name)),
                    pharmacy_type="Farmácias do Componente Especializado (Alto Custo - CEAF)",
                    latitude=lat,
                    longitude=lng,
                    google_maps_url=direct_url,
                    google_maps_embed=embed_url,
                    contact_email=str(meta.get("email", "")),
                    covered_ras=list(meta.get("ras", [])),
                )
            )

        # 4. Decodifica todas as 228 unidades (UBS e Atenção Secundária) de `Estabelecimentos`
        total_estab = 0
        geolocated_estab = 0
        if raw_doc_maps.get("results"):
            ds_estab = raw_doc_maps["results"][0]["result"]["data"]["dsr"]["DS"][0]
            estab_rows = decode_powerbi_dsr(ds_estab)
            total_estab = len(estab_rows)
            for erow in estab_rows:
                cnes = str(erow[0] or "")
                name = str(erow[1] or "")
                address = str(erow[2] or "")
                bairro = str(erow[3] or "")
                ptype = str(erow[4] or "")
                lat_val = float(erow[5]) if erow[5] is not None else None
                lng_val = float(erow[6]) if erow[6] is not None else None
                if lat_val is not None and lng_val is not None:
                    geolocated_estab += 1
                    gmaps_url = f"https://www.google.com/maps/search/?api=1&query={lat_val},{lng_val}"
                else:
                    gmaps_url = (
                        f"https://www.google.com/maps/search/?api=1&query={name}+{bairro}+DF"
                    )
                pharmacies.append(
                    GeolocatedPharmacy(
                        cnes=cnes,
                        name=name,
                        address=address,
                        neighborhood_or_ra=bairro,
                        pharmacy_type=ptype,
                        latitude=lat_val,
                        longitude=lng_val,
                        google_maps_url=gmaps_url,
                    )
                )

        # Estatísticas de estoque
        by_status = dict(Counter(item.disp_estoque for item in stock_items))
        by_unit: dict[str, dict[str, int]] = {}
        for unit in ("Asa Sul", "Ceilândia", "Gama"):
            unit_items = [i for i in stock_items if i.unidade == unit]
            by_unit[unit] = dict(Counter(i.disp_estoque for i in unit_items))

        distinct_meds = len({i.desc_produto for i in stock_items if i.desc_produto})

        stock_payload_out = {
            "source_url": "https://info.saude.df.gov.br/saude-do-cidadao/painel-infosaude-farmacias-de-alto-custo/estoque-de-medicamentos/",
            "powerbi_api_endpoint": POWERBI_QUERY_ENDPOINT,
            "resource_key": CEAF_RESOURCE_KEY,
            "panel_updated_at_utc": panel_updated_utc,
            "update_schedule": "Diária (00:00 BRT e atualização intradiária ~13:45-14:37 BRT)",
            "total_records": len(stock_items),
            "distinct_medications": distinct_meds,
            "stock_by_status": by_status,
            "stock_by_unit": by_unit,
            "items": [item.to_dict() for item in stock_items],
        }
        maps_payload_out = {
            "source_url": "https://info.saude.df.gov.br/como-garantir-seu-medicamento/",
            "powerbi_api_endpoint": POWERBI_QUERY_ENDPOINT,
            "ceaf_resource_key": CEAF_RESOURCE_KEY,
            "establishments_resource_key": DOC_MAPS_RESOURCE_KEY,
            "update_schedule": "Semanal (Segundas-feiras às 00:19 BRT)",
            "total_establishments": len(pharmacies),
            "geolocated_with_lat_lng": geolocated_estab + len(ceaf_results),
            "pharmacies": [p.to_dict() for p in pharmacies],
        }

        stock_json_str = json.dumps(stock_payload_out, ensure_ascii=False, indent=2)
        maps_json_str = json.dumps(maps_payload_out, ensure_ascii=False, indent=2)

        self.stock_path.write_text(stock_json_str, encoding="utf-8")
        self.maps_path.write_text(maps_json_str, encoding="utf-8")

        return InfoSaudeSyncSummary(
            synced_at_utc=datetime.now(UTC).isoformat(),
            ceaf_panel_updated_at_utc=panel_updated_utc,
            stock_update_schedule="Diária (2x ao dia: 00:00 BRT e ~13:45–14:37 BRT)",
            catalog_update_schedule="Semanal (Segundas-feiras às 00:19 BRT)",
            total_ceaf_stock_rows=len(stock_items),
            distinct_ceaf_medications=distinct_meds,
            stock_by_status=by_status,
            stock_by_unit=by_unit,
            total_establishments=total_estab,
            geolocated_establishments=geolocated_estab,
            ceaf_units_with_maps=len(ceaf_results),
            stock_sha256=compute_sha256(stock_json_str),
            maps_sha256=compute_sha256(maps_json_str),
        )

    def query_medication_stock(
        self, medication_query: str, unit_filter: str | None = None
    ) -> list[CEAFLiveStockItem]:
        """Consulta a disponibilidade em tempo real de um medicamento nas unidades do CEAF-DF."""
        if not self.stock_path.exists():
            return []
        data = json.loads(self.stock_path.read_text(encoding="utf-8"))
        norm_q = normalize_pt_text(medication_query)
        q_tokens = [t for t in norm_q.split() if len(t) > 2]

        matches: list[CEAFLiveStockItem] = []
        for raw in data.get("items", []):
            norm_desc = normalize_pt_text(raw["desc_produto"])
            if not all(tok in norm_desc for tok in q_tokens):
                continue
            if unit_filter and normalize_pt_text(unit_filter) not in normalize_pt_text(
                raw["unidade"]
            ):
                continue
            matches.append(
                CEAFLiveStockItem(
                    cod_produto=raw["cod_produto"],
                    desc_produto=raw["desc_produto"],
                    unidade=raw["unidade"],
                    disp_estoque=raw["disp_estoque"],
                    origem_abastecimento=raw["origem_abastecimento"],
                    psicotropico=raw["psicotropico"],
                    ultima_atualizacao=raw["ultima_atualizacao"],
                )
            )
        return matches

    def find_pharmacies_by_ra(
        self, ra_query: str, top_k: int = 5
    ) -> list[GeolocatedPharmacy]:
        """Retorna as farmácias (CEAF e UBS) que atendem uma Região Administrativa (RA) do DF."""
        if not self.maps_path.exists():
            return []
        data = json.loads(self.maps_path.read_text(encoding="utf-8"))
        norm_ra = normalize_pt_text(ra_query)

        matched: list[GeolocatedPharmacy] = []
        for raw in data.get("pharmacies", []):
            covered = [normalize_pt_text(r) for r in (raw.get("covered_ras") or [])]
            norm_bairro = normalize_pt_text(raw.get("neighborhood_or_ra", ""))
            norm_name = normalize_pt_text(raw.get("name", ""))
            if (
                norm_ra in norm_bairro
                or norm_ra in norm_name
                or any(norm_ra in c for c in covered)
            ):
                matched.append(
                    GeolocatedPharmacy(
                        cnes=raw["cnes"],
                        name=raw["name"],
                        address=raw["address"],
                        neighborhood_or_ra=raw["neighborhood_or_ra"],
                        pharmacy_type=raw["pharmacy_type"],
                        latitude=raw.get("latitude"),
                        longitude=raw.get("longitude"),
                        google_maps_url=raw["google_maps_url"],
                        google_maps_embed=raw.get("google_maps_embed", ""),
                        contact_email=raw.get("contact_email", ""),
                        covered_ras=raw.get("covered_ras"),
                    )
                )
        return matched[:top_k]

