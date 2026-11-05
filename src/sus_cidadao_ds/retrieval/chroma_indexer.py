"""Gerenciador e Indexador Automatizado de Coleções Vetoriais no ChromaDB (SPEC-07).

Indexa os dados estruturados em JSON das camadas Silver e Gold em 3 coleções especializadas:
1. `ceaf_live_stock`: Disponibilidade em tempo real das farmácias de alto custo (Asa Sul, Ceilândia, Gama).
2. `df_pharmacies`: Geolocalização, endereços e rotas no Google Maps de farmácias de UBS, Hospitais e CEAF.
3. `sus_normative_protocols`: Portarias oficiais (RENAME 2024, Farmácia Popular, REME-DF, SISREG III/CPPAS).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings

from sus_cidadao_ds.core.config import ProjectPaths


@dataclass(frozen=True)
class ChromaSearchResult:
    """Resultado individual de consulta semântica no ChromaDB."""

    id: str
    document: str
    metadata: dict[str, Any]
    distance: float
    relevance_score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ChromaIndexingSummary:
    """Resumo consolidado da indexação vetorial no ChromaDB."""

    vectorstore_path: str
    stock_count: int
    pharmacies_count: int
    protocols_count: int
    unified_pdf_count: int
    total_indexed: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ChromaVectorStoreManager:
    """Gerencia a ingestão, persistência e busca semântica multi-coleção no ChromaDB."""

    COLLECTION_STOCK = "ceaf_live_stock"
    COLLECTION_PHARMACIES = "df_pharmacies"
    COLLECTION_PROTOCOLS = "sus_normative_protocols"
    COLLECTION_UNIFIED_PDF_CORPUS = "sus_unified_pdf_corpus"

    def __init__(self, vectorstore_dir: Path | None = None) -> None:
        if vectorstore_dir is None:
            paths = ProjectPaths.from_root()
            self.vectorstore_dir = paths.data_dir / "vectorstore"
        else:
            self.vectorstore_dir = vectorstore_dir

        self.vectorstore_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(self.vectorstore_dir),
            settings=Settings(anonymized_telemetry=False),
        )

    def _get_or_create_col(self, name: str) -> chromadb.Collection:
        return self.client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    def index_ceaf_stock(self, stock_json_path: Path) -> int:
        """Textualiza e indexa em lote o estoque em tempo real das Farmácias de Alto Custo (CEAF)."""
        if not stock_json_path.exists():
            return 0
        data = json.loads(stock_json_path.read_text(encoding="utf-8"))
        items = data.get("items", [])
        if not items:
            return 0

        col = self._get_or_create_col(self.COLLECTION_STOCK)
        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []

        for item in items:
            cod = str(item["cod_produto"]).strip()
            desc = str(item["desc_produto"]).strip()
            unidade = str(item["unidade"]).strip()
            disp = str(item["disp_estoque"]).strip()
            origem = str(item.get("origem_abastecimento", "SES-DF")).strip()
            psico = str(item.get("psicotropico", "Outros")).strip()
            att = str(item.get("ultima_atualizacao", "")).strip()

            safe_unit = unidade.upper().replace(" ", "_")
            safe_origem = origem.upper().replace(" ", "_").replace("-", "_")
            doc_id = f"ESTOQUE_{safe_unit}_{safe_origem}_{cod}"

            doc_text = (
                f"Medicamento do Componente Especializado (Alto Custo): {desc} (Código SES: {cod}).\n"
                f"Unidade de Retirada: Farmácia de Alto Custo de {unidade} (CEAF-DF).\n"
                f"Disponibilidade em Estoque: {disp}.\n"
                f"Origem do Abastecimento: {origem}.\n"
                f"Classificação do Medicamento: {psico}.\n"
                f"Última atualização registrada no InfoSaúde-DF: {att}."
            )

            meta: dict[str, Any] = {
                "tipo_dado": "estoque_ceaf",
                "cod_produto": cod,
                "unidade": unidade,
                "disp_estoque": disp,
                "tem_estoque": "COM ESTOQUE" in disp.upper(),
                "origem": origem,
            }

            ids.append(doc_id)
            documents.append(doc_text)
            metadatas.append(meta)

        self._batch_upsert(col, ids, documents, metadatas)
        return len(ids)

    def index_df_pharmacies(self, pharmacies_json_path: Path) -> int:
        """Textualiza e indexa em lote as farmácias e estabelecimentos de saúde do DF com geolocalização."""
        if not pharmacies_json_path.exists():
            return 0
        data = json.loads(pharmacies_json_path.read_text(encoding="utf-8"))
        pharmacies = data.get("pharmacies", [])
        if not pharmacies:
            return 0

        col = self._get_or_create_col(self.COLLECTION_PHARMACIES)
        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []

        for p in pharmacies:
            cnes = str(p.get("cnes", "")).strip()
            name = str(p.get("name", "")).strip()
            address = str(p.get("address", "")).strip()
            bairro = str(p.get("neighborhood_or_ra", "")).strip()
            ptype = str(p.get("pharmacy_type", "")).strip()
            lat = p.get("latitude")
            lng = p.get("longitude")
            gmaps_url = str(p.get("google_maps_url", "")).strip()
            email = str(p.get("contact_email", "")).strip()
            covered = p.get("covered_ras") or []

            doc_id = f"FARMACIA_{cnes or name.upper().replace(' ', '_')}"

            coords_desc = (
                f"Latitude {lat}, Longitude {lng}"
                if lat is not None and lng is not None
                else "Coordenadas exatas não informadas no cadastro oficial"
            )
            covered_desc = (
                f"Regiões Administrativas cobertas: {', '.join(covered)}."
                if covered
                else ""
            )
            email_desc = f"E-mail de Contato: {email}." if email else ""

            doc_text = (
                f"Estabelecimento de Saúde / Farmácia: {name} (CNES: {cnes}).\n"
                f"Tipo de Dispensação: {ptype}.\n"
                f"Endereço: {address}, {bairro} - Distrito Federal.\n"
                f"Localização Geográfica: {coords_desc}.\n"
                f"Link Google Maps: {gmaps_url}.\n"
                f"{covered_desc}\n"
                f"{email_desc}"
            ).strip()

            meta: dict[str, Any] = {
                "tipo_dado": "estabelecimento_saude",
                "cnes": cnes,
                "bairro_ou_ra": bairro,
                "tipo_farmacia": ptype,
                "tem_coordenadas": lat is not None and lng is not None,
                "latitude": float(lat) if lat is not None else 0.0,
                "longitude": float(lng) if lng is not None else 0.0,
            }

            ids.append(doc_id)
            documents.append(doc_text)
            metadatas.append(meta)

        self._batch_upsert(col, ids, documents, metadatas)
        return len(ids)

    def index_normative_protocols(
        self, chunks_json_path: Path, canonical_meds_json_path: Path
    ) -> int:
        """Textualiza e indexa em lote os chunks de portarias normativas e o catálogo canônico."""
        col = self._get_or_create_col(self.COLLECTION_PROTOCOLS)
        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []

        if chunks_json_path.exists():
            chunks_data = json.loads(chunks_json_path.read_text(encoding="utf-8"))
            for chunk in chunks_data:
                cid = str(chunk["chunk_id"])
                doc_text = (
                    f"Documento Oficial: {chunk['document_title']}.\n"
                    f"Seção: {chunk['section']} (Página {chunk['page_number']}).\n"
                    f"Categoria da Rota: {chunk['route_category']}.\n"
                    f"Texto Normativo: {chunk['text']}\n"
                    f"Medicamentos DCB Citados: {', '.join(chunk.get('dcb_mentions', []))}."
                )
                meta: dict[str, Any] = {
                    "tipo_dado": "chunk_normativo",
                    "source_id": str(chunk["source_id"]),
                    "route_category": str(chunk["route_category"]),
                    "page_number": int(chunk["page_number"]),
                }
                ids.append(f"CHUNK_{cid}")
                documents.append(doc_text)
                metadatas.append(meta)

        if canonical_meds_json_path.exists():
            meds_data = json.loads(
                canonical_meds_json_path.read_text(encoding="utf-8")
            )
            for med in meds_data:
                mid = str(med["medication_id"])
                docs_req = ", ".join(med.get("required_documents", []))
                doc_text = (
                    f"Medicamento Canônico SUS: {med['dcb_name']} {med['concentration']} ({med['pharmaceutical_form']}).\n"
                    f"Componente RENAME: {med['rename_component']}.\n"
                    f"Rota de Dispensação: {med['dispensation_route']}.\n"
                    f"Disponível no Farmácia Popular: {med['available_pfpb']} (100% Gratuito: {med['pfpb_free']}).\n"
                    f"Disponível na REME-DF: {med['available_reme_df']}.\n"
                    f"Exige Processo LME: {med['requires_lme']}.\n"
                    f"Validade da Receita: {med['prescription_validity_days']} dias.\n"
                    f"Documentos Obrigatórios: {docs_req}.\n"
                    f"Observações: {med.get('notes', '')}"
                )
                meta = {
                    "tipo_dado": "medicamento_canonico",
                    "dcb_name": str(med["dcb_name"]).lower(),
                    "dispensation_route": str(med["dispensation_route"]),
                    "requires_lme": bool(med["requires_lme"]),
                    "pfpb_free": bool(med["pfpb_free"]),
                }
                ids.append(f"CANONICAL_{mid}")
                documents.append(doc_text)
                metadatas.append(meta)

        self._batch_upsert(col, ids, documents, metadatas)
        return len(ids)

    def index_unified_pdf_chunks(self, chunks_json_path: Path) -> int:
        """Textualiza e indexa em lote os chunks extraídos de todos os PDFs oficiais e convertidos (SPEC-08)."""
        if not chunks_json_path.exists():
            return 0
        chunks = json.loads(chunks_json_path.read_text(encoding="utf-8"))
        if not chunks:
            return 0

        col = self._get_or_create_col(self.COLLECTION_UNIFIED_PDF_CORPUS)
        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []

        for ch in chunks:
            cid = str(ch["chunk_id"]).strip()
            content = str(ch["content"]).strip()
            src_pdf = str(ch.get("source_pdf", "")).strip()
            category = str(ch.get("category", "documento_geral")).strip()
            page = int(ch.get("page_number", 1))
            chars = int(ch.get("char_count", len(content)))

            meta: dict[str, Any] = {
                "tipo_dado": "pdf_chunk",
                "source_pdf": src_pdf,
                "category": category,
                "page_number": page,
                "char_count": chars,
            }

            ids.append(f"PDF_{cid}")
            documents.append(content)
            metadatas.append(meta)

        self._batch_upsert(col, ids, documents, metadatas)
        return len(ids)

    def index_all(self, paths: ProjectPaths) -> ChromaIndexingSummary:
        """Executa a indexação completa de todas as coleções, incluindo o corpus unificado de PDFs."""
        stock_path = paths.gold_dir / "ceaf_live_stock.json"
        pharmacies_path = paths.gold_dir / "df_pharmacies_geolocated.json"
        chunks_path = paths.silver_dir / "normative_chunks.json"
        canonical_path = paths.gold_dir / "medicamentos_sus_canonical.json"
        unified_chunks_path = paths.silver_dir / "unified_pdf_chunks.json"

        n_stock = self.index_ceaf_stock(stock_path)
        n_pharm = self.index_df_pharmacies(pharmacies_path)
        n_proto = self.index_normative_protocols(chunks_path, canonical_path)
        n_unified = self.index_unified_pdf_chunks(unified_chunks_path)

        return ChromaIndexingSummary(
            vectorstore_path=str(self.vectorstore_dir),
            stock_count=n_stock,
            pharmacies_count=n_pharm,
            protocols_count=n_proto,
            unified_pdf_count=n_unified,
            total_indexed=n_stock + n_pharm + n_proto + n_unified,
        )

    def search_unified_corpus(
        self,
        query: str,
        category: str | None = None,
        top_k: int = 5,
    ) -> list[ChromaSearchResult]:
        """Realiza busca semântica no corpus unificado de PDFs oficiais e relatórios gerados."""
        where_filter = {"category": category} if category else None
        return self.search(
            query=query,
            collection_name=self.COLLECTION_UNIFIED_PDF_CORPUS,
            where_filter=where_filter,
            top_k=top_k,
        )

    def search(
        self,
        query: str,
        collection_name: str,
        where_filter: dict[str, Any] | None = None,
        top_k: int = 5,
    ) -> list[ChromaSearchResult]:
        """Realiza busca por similaridade semântica (cosseno) com filtro opcional por metadados."""
        col = self.client.get_collection(name=collection_name)
        kwargs: dict[str, Any] = {
            "query_texts": [query],
            "n_results": top_k,
        }
        if where_filter:
            kwargs["where"] = where_filter

        results = col.query(**kwargs)
        search_hits: list[ChromaSearchResult] = []

        ids_raw = results.get("ids") or [[]]
        docs_raw = results.get("documents") or [[]]
        metas_raw = results.get("metadatas") or [[]]
        dists_raw = results.get("distances") or [[]]

        ids_list = ids_raw[0] if ids_raw else []
        docs_list = docs_raw[0] if docs_raw else []
        metas_list = metas_raw[0] if metas_raw else []
        dists_list = dists_raw[0] if dists_raw else []

        for doc_id, doc_text, meta, dist in zip(
            ids_list, docs_list, metas_list, dists_list, strict=True
        ):
            # No espaço cosseno do ChromaDB, relevância pode ser derivada como 1 - dist
            relevance = max(0.0, 1.0 - float(dist)) if dist is not None else 0.0
            search_hits.append(
                ChromaSearchResult(
                    id=str(doc_id),
                    document=str(doc_text),
                    metadata=dict(meta) if meta else {},
                    distance=round(float(dist), 4) if dist is not None else 0.0,
                    relevance_score=round(relevance, 4),
                )
            )
        return search_hits

    def _batch_upsert(
        self,
        col: chromadb.Collection,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]],
        batch_size: int = 200,
    ) -> None:
        """Divide a inserção em lotes seguros para otimizar tempo e uso de memória."""
        total = len(ids)
        for i in range(0, total, batch_size):
            b_ids = ids[i : i + batch_size]
            b_docs = documents[i : i + batch_size]
            b_metas = metadatas[i : i + batch_size]
            col.upsert(
                ids=b_ids,
                documents=b_docs,
                metadatas=b_metas,  # type: ignore[arg-type]
            )
