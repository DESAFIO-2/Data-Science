"""Sincronizador de artefatos entre DESAFIO-2/engenharia-dados e Data-Science.

Suporta:
1. Importação direta de um diretório local `engenharia-dados` (camadas silver/gold).
2. Materialização determinística das bases canônicas RENAME 2024, Farmácia Popular (PFPB),
   REME-DF e SISREG III/CPPAS com verificação de integridade SHA-256.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import shutil

from sus_cidadao_ds.contracts.schemas import (
    CanonicalMedication,
    DataManifest,
    NormativeChunk,
    compute_sha256,
)
from sus_cidadao_ds.core.config import ProjectPaths


def _build_canonical_medications() -> list[CanonicalMedication]:
    """Constrói o catálogo canônico (Gold) auditado pelas regras RENAME 2024, PFPB e REME-DF."""
    docs_pfpb = [
        "Documento oficial com foto e CPF",
        "Receita médica válida (SUS ou particular) com CRM, carimbo e data",
    ]
    docs_ubs = [
        "Cartão Nacional de Saúde (CNS / Cartão SUS)",
        "Documento oficial com foto e CPF",
        "Receita médica válida em duas vias (SUS ou particular)",
    ]
    docs_ceaf = [
        "Laudo de Solicitação, Avaliação e Autorização de Medicamento(s) (LME) preenchido pelo médico",
        "Receita médica em duas vias com DCB (nome genérico)",
        "Cartão Nacional de Saúde (CNS) e Documento com CPF",
        "Comprovante de residência no Distrito Federal",
        "Exames laboratoriais/imagem exigidos pelo PCDT da doença (CID-10)",
    ]

    raw_items: list[CanonicalMedication] = [
        # --- FARMÁCIA POPULAR DO BRASIL (100% Gratuitos - PFPB + RENAME Básico) ---
        CanonicalMedication(
            medication_id="MED-LOSARTANA-50MG",
            dcb_name="losartana potássica",
            concentration="50 mg",
            pharmaceutical_form="comprimido",
            rename_component="Básico",
            available_pfpb=True,
            pfpb_free=True,
            available_reme_df=True,
            dispensation_route="FARMACIA_POPULAR",
            requires_lme=False,
            icd10_codes=["I10", "I11"],
            required_documents=docs_pfpb,
            prescription_validity_days=180,
            source_id="PFPB_2024",
            source_page=14,
            notes="100% gratuito no Programa Farmácia Popular (drogarias credenciadas) e disponível nas UBS do DF.",
        ),
        CanonicalMedication(
            medication_id="MED-METFORMINA-500MG",
            dcb_name="cloridrato de metformina",
            concentration="500 mg",
            pharmaceutical_form="comprimido",
            rename_component="Básico",
            available_pfpb=True,
            pfpb_free=True,
            available_reme_df=True,
            dispensation_route="FARMACIA_POPULAR",
            requires_lme=False,
            icd10_codes=["E11"],
            required_documents=docs_pfpb,
            prescription_validity_days=180,
            source_id="PFPB_2024",
            source_page=11,
            notes="100% gratuito na Farmácia Popular para Diabetes Mellitus e nas UBS.",
        ),
        CanonicalMedication(
            medication_id="MED-METFORMINA-850MG",
            dcb_name="cloridrato de metformina",
            concentration="850 mg",
            pharmaceutical_form="comprimido",
            rename_component="Básico",
            available_pfpb=True,
            pfpb_free=True,
            available_reme_df=True,
            dispensation_route="FARMACIA_POPULAR",
            requires_lme=False,
            icd10_codes=["E11"],
            required_documents=docs_pfpb,
            prescription_validity_days=180,
            source_id="PFPB_2024",
            source_page=11,
            notes="100% gratuito na Farmácia Popular e UBS.",
        ),
        CanonicalMedication(
            medication_id="MED-ENALAPRIL-10MG",
            dcb_name="maleato de enalapril",
            concentration="10 mg",
            pharmaceutical_form="comprimido",
            rename_component="Básico",
            available_pfpb=True,
            pfpb_free=True,
            available_reme_df=True,
            dispensation_route="FARMACIA_POPULAR",
            requires_lme=False,
            icd10_codes=["I10", "I50"],
            required_documents=docs_pfpb,
            prescription_validity_days=180,
            source_id="PFPB_2024",
            source_page=13,
            notes="100% gratuito na Farmácia Popular para hipertensão arterial.",
        ),
        CanonicalMedication(
            medication_id="MED-ATENOLOL-25MG",
            dcb_name="atenolol",
            concentration="25 mg",
            pharmaceutical_form="comprimido",
            rename_component="Básico",
            available_pfpb=True,
            pfpb_free=True,
            available_reme_df=True,
            dispensation_route="FARMACIA_POPULAR",
            requires_lme=False,
            icd10_codes=["I10", "I20"],
            required_documents=docs_pfpb,
            prescription_validity_days=180,
            source_id="PFPB_2024",
            source_page=12,
            notes="100% gratuito na Farmácia Popular e UBS.",
        ),
        CanonicalMedication(
            medication_id="MED-HIDROCLOROTIAZIDA-25MG",
            dcb_name="hidroclorotiazida",
            concentration="25 mg",
            pharmaceutical_form="comprimido",
            rename_component="Básico",
            available_pfpb=True,
            pfpb_free=True,
            available_reme_df=True,
            dispensation_route="FARMACIA_POPULAR",
            requires_lme=False,
            icd10_codes=["I10"],
            required_documents=docs_pfpb,
            prescription_validity_days=180,
            source_id="PFPB_2024",
            source_page=13,
            notes="Diurético tiazídico 100% gratuito na Farmácia Popular e UBS.",
        ),
        CanonicalMedication(
            medication_id="MED-ANLODIPINO-5MG",
            dcb_name="besilato de anlodipino",
            concentration="5 mg",
            pharmaceutical_form="comprimido",
            rename_component="Básico",
            available_pfpb=True,
            pfpb_free=True,
            available_reme_df=True,
            dispensation_route="FARMACIA_POPULAR",
            requires_lme=False,
            icd10_codes=["I10"],
            required_documents=docs_pfpb,
            prescription_validity_days=180,
            source_id="PFPB_2024",
            source_page=12,
            notes="100% gratuito na Farmácia Popular (elenco de hipertensão).",
        ),
        CanonicalMedication(
            medication_id="MED-SINVASTATINA-20MG",
            dcb_name="sinvastatina",
            concentration="20 mg",
            pharmaceutical_form="comprimido",
            rename_component="Básico",
            available_pfpb=True,
            pfpb_free=True,
            available_reme_df=True,
            dispensation_route="FARMACIA_POPULAR",
            requires_lme=False,
            icd10_codes=["E78.0", "E78.5"],
            required_documents=docs_pfpb,
            prescription_validity_days=180,
            source_id="PFPB_2024",
            source_page=16,
            notes="Dislipidemia: 100% gratuito no Programa Farmácia Popular (gratuidade expandida).",
        ),
        CanonicalMedication(
            medication_id="MED-GLIBENCLAMIDA-5MG",
            dcb_name="glibenclamida",
            concentration="5 mg",
            pharmaceutical_form="comprimido",
            rename_component="Básico",
            available_pfpb=True,
            pfpb_free=True,
            available_reme_df=True,
            dispensation_route="FARMACIA_POPULAR",
            requires_lme=False,
            icd10_codes=["E11"],
            required_documents=docs_pfpb,
            prescription_validity_days=180,
            source_id="PFPB_2024",
            source_page=11,
            notes="Hipoglicemiante oral 100% gratuito na Farmácia Popular.",
        ),
        CanonicalMedication(
            medication_id="MED-INSULINA-NPH-100UI",
            dcb_name="insulina humana nph",
            concentration="100 UI/mL",
            pharmaceutical_form="suspensão injetável",
            rename_component="Básico",
            available_pfpb=True,
            pfpb_free=True,
            available_reme_df=True,
            dispensation_route="FARMACIA_POPULAR",
            requires_lme=False,
            icd10_codes=["E10", "E11"],
            required_documents=docs_pfpb,
            prescription_validity_days=180,
            source_id="PFPB_2024",
            source_page=11,
            notes="Insulina NPH 100% gratuita na Farmácia Popular e UBS.",
        ),
        CanonicalMedication(
            medication_id="MED-SALBUTAMOL-100MCG",
            dcb_name="sulfato de salbutamol",
            concentration="100 mcg/dose",
            pharmaceutical_form="aerossol oral",
            rename_component="Básico",
            available_pfpb=True,
            pfpb_free=True,
            available_reme_df=True,
            dispensation_route="FARMACIA_POPULAR",
            requires_lme=False,
            icd10_codes=["J45"],
            required_documents=docs_pfpb,
            prescription_validity_days=180,
            source_id="PFPB_2024",
            source_page=10,
            notes="100% gratuito na Farmácia Popular para tratamento de asma.",
        ),
        CanonicalMedication(
            medication_id="MED-ALENDRONATO-70MG",
            dcb_name="alendronato de sódio",
            concentration="70 mg",
            pharmaceutical_form="comprimido",
            rename_component="Básico",
            available_pfpb=True,
            pfpb_free=True,
            available_reme_df=True,
            dispensation_route="FARMACIA_POPULAR",
            requires_lme=False,
            icd10_codes=["M80", "M81"],
            required_documents=docs_pfpb,
            prescription_validity_days=180,
            source_id="PFPB_2024",
            source_page=17,
            notes="Osteoporose: 100% gratuito na Farmácia Popular (gratuidade expandida).",
        ),
        CanonicalMedication(
            medication_id="MED-DAPAGLIFLOZINA-10MG",
            dcb_name="dapagliflozina",
            concentration="10 mg",
            pharmaceutical_form="comprimido",
            rename_component="Especializado",
            available_pfpb=True,
            pfpb_free=True,
            available_reme_df=True,
            dispensation_route="FARMACIA_POPULAR",
            requires_lme=False,
            icd10_codes=["E11", "I50"],
            required_documents=docs_pfpb,
            prescription_validity_days=180,
            source_id="PFPB_2024",
            source_page=12,
            notes="Gratuidade na Farmácia Popular para DM2 associada a doença cardiovascular (>= 65 anos) ou via CEAF.",
        ),
        # --- UNIDADE BÁSICA DE SAÚDE (UBS - RENAME 2024 Básico + REME-DF) ---
        CanonicalMedication(
            medication_id="MED-OMEPRAZOL-20MG",
            dcb_name="omeprazol",
            concentration="20 mg",
            pharmaceutical_form="cápsula",
            rename_component="Básico",
            available_pfpb=False,
            pfpb_free=False,
            available_reme_df=True,
            dispensation_route="UBS_ATENCAO_PRIMARIA",
            requires_lme=False,
            icd10_codes=["K21", "K25", "K29"],
            required_documents=docs_ubs,
            prescription_validity_days=180,
            source_id="RENAME_2024",
            source_page=48,
            notes="Não consta na Farmácia Popular. Retirada gratuita exclusivamente na Farmácia da UBS de referência.",
        ),
        CanonicalMedication(
            medication_id="MED-LEVOTIROXINA-50MCG",
            dcb_name="levotiroxina sódica",
            concentration="50 mcg",
            pharmaceutical_form="comprimido",
            rename_component="Básico",
            available_pfpb=False,
            pfpb_free=False,
            available_reme_df=True,
            dispensation_route="UBS_ATENCAO_PRIMARIA",
            requires_lme=False,
            icd10_codes=["E03.9"],
            required_documents=docs_ubs,
            prescription_validity_days=180,
            source_id="RENAME_2024",
            source_page=44,
            notes="Componente Básico (RENAME 2024 e REME-DF). Retirada gratuita nas UBS da SES-DF.",
        ),
        CanonicalMedication(
            medication_id="MED-AMOXICILINA-500MG",
            dcb_name="amoxicilina",
            concentration="500 mg",
            pharmaceutical_form="cápsula",
            rename_component="Básico",
            available_pfpb=False,
            pfpb_free=False,
            available_reme_df=True,
            dispensation_route="UBS_ATENCAO_PRIMARIA",
            requires_lme=False,
            icd10_codes=["J01", "J02", "J03"],
            required_documents=[
                "Cartão Nacional de Saúde (CNS)",
                "Documento com CPF",
                "Receita de controle antimicrobiano em 2 vias (validade de 10 dias)",
            ],
            prescription_validity_days=10,
            source_id="RENAME_2024",
            source_page=32,
            notes="Antimicrobiano do Componente Básico. Receita válida por 10 dias com retenção da 2ª via na UBS.",
        ),
        CanonicalMedication(
            medication_id="MED-FLUOXETINA-20MG",
            dcb_name="cloridrato de fluoxetina",
            concentration="20 mg",
            pharmaceutical_form="cápsula",
            rename_component="Básico",
            available_pfpb=False,
            pfpb_free=False,
            available_reme_df=True,
            dispensation_route="UBS_ATENCAO_PRIMARIA",
            requires_lme=False,
            icd10_codes=["F32", "F33", "F41"],
            required_documents=[
                "Cartão Nacional de Saúde (CNS) e CPF",
                "Receita de Controle Especial (Branca em 2 vias - Portaria 344/98, validade 30 dias)",
            ],
            prescription_validity_days=30,
            source_id="REME_DF_2024",
            source_page=29,
            notes="Psicotrópico (Lista C1). Retirada gratuita na farmácia da UBS com retenção de via.",
        ),
        CanonicalMedication(
            medication_id="MED-CARBAMAZEPINA-200MG",
            dcb_name="carbamazepina",
            concentration="200 mg",
            pharmaceutical_form="comprimido",
            rename_component="Básico",
            available_pfpb=False,
            pfpb_free=False,
            available_reme_df=True,
            dispensation_route="UBS_ATENCAO_PRIMARIA",
            requires_lme=False,
            icd10_codes=["G40", "F31"],
            required_documents=[
                "Cartão Nacional de Saúde (CNS) e CPF",
                "Receita de Controle Especial em 2 vias (Portaria 344/98, validade 30 dias)",
            ],
            prescription_validity_days=30,
            source_id="REME_DF_2024",
            source_page=27,
            notes="Anticonvulsivante do Componente Básico na REME-DF. Dispensado na UBS.",
        ),
        # --- FARMÁCIA DE ALTO CUSTO / COMPONENTE ESPECIALIZADO (CEAF - LME) ---
        CanonicalMedication(
            medication_id="MED-ADALIMUMABE-40MG",
            dcb_name="adalimumabe",
            concentration="40 mg",
            pharmaceutical_form="solução injetável",
            rename_component="Especializado",
            available_pfpb=False,
            pfpb_free=False,
            available_reme_df=True,
            dispensation_route="ALTO_CUSTO_CEAF",
            requires_lme=True,
            icd10_codes=["M05.0", "M06.0", "M45", "K50.0"],
            required_documents=docs_ceaf,
            prescription_validity_days=90,
            source_id="RENAME_2024",
            source_page=112,
            notes="Componente Especializado (CEAF). Exige abertura de processo com LME (renovação trimestral) nas unidades da Farmácia de Alto Custo do DF (102 Sul, Ceilândia ou Gama).",
        ),
        CanonicalMedication(
            medication_id="MED-ATORVASTATINA-40MG",
            dcb_name="atorvastatina cálcica",
            concentration="40 mg",
            pharmaceutical_form="comprimido",
            rename_component="Especializado",
            available_pfpb=False,
            pfpb_free=False,
            available_reme_df=True,
            dispensation_route="ALTO_CUSTO_CEAF",
            requires_lme=True,
            icd10_codes=["E78.0", "E78.2"],
            required_documents=docs_ceaf,
            prescription_validity_days=90,
            source_id="RENAME_2024",
            source_page=118,
            notes="Componente Especializado (CEAF). Exige LME e perfil lipídico conforme PCDT de Dislipidemia.",
        ),
        CanonicalMedication(
            medication_id="MED-SACUBITRIL-VALSARTANA-97-103MG",
            dcb_name="sacubitril valsartana sódica hidratada",
            concentration="97 mg + 103 mg",
            pharmaceutical_form="comprimido",
            rename_component="Especializado",
            available_pfpb=False,
            pfpb_free=False,
            available_reme_df=True,
            dispensation_route="ALTO_CUSTO_CEAF",
            requires_lme=True,
            icd10_codes=["I50.0"],
            required_documents=docs_ceaf,
            prescription_validity_days=90,
            source_id="RENAME_2024",
            source_page=141,
            notes="Insuficiência Cardíaca com fração de ejeção reduzida (FEVE <= 35%). Dispensação via Farmácia de Alto Custo mediante LME e Ecocardiograma.",
        ),
        CanonicalMedication(
            medication_id="MED-FORMOTEROL-BUDESONIDA-12-400MCG",
            dcb_name="fumarato de formoterol di-hidratado + budesonida",
            concentration="12 mcg + 400 mcg",
            pharmaceutical_form="cápsula inalante",
            rename_component="Especializado",
            available_pfpb=False,
            pfpb_free=False,
            available_reme_df=True,
            dispensation_route="ALTO_CUSTO_CEAF",
            requires_lme=True,
            icd10_codes=["J45.0", "J44.8"],
            required_documents=docs_ceaf,
            prescription_validity_days=90,
            source_id="RENAME_2024",
            source_page=125,
            notes="Componente Especializado para Asma Persistente Moderada/Grave e DPOC. Exige LME e espirometria.",
        ),
        CanonicalMedication(
            medication_id="MED-QUETIAPINA-25MG",
            dcb_name="hemifumarato de quetiapina",
            concentration="25 mg",
            pharmaceutical_form="comprimido",
            rename_component="Especializado",
            available_pfpb=False,
            pfpb_free=False,
            available_reme_df=True,
            dispensation_route="ALTO_CUSTO_CEAF",
            requires_lme=True,
            icd10_codes=["F20.0", "F31.3"],
            required_documents=docs_ceaf,
            prescription_validity_days=90,
            source_id="RENAME_2024",
            source_page=130,
            notes="Componente Especializado (CEAF). Exige LME + Receita de Controle Especial em duas vias.",
        ),
        CanonicalMedication(
            medication_id="MED-INSULINA-GLARGINA-100UI",
            dcb_name="insulina glargina",
            concentration="100 UI/mL",
            pharmaceutical_form="solução injetável",
            rename_component="Especializado",
            available_pfpb=False,
            pfpb_free=False,
            available_reme_df=True,
            dispensation_route="ALTO_CUSTO_CEAF",
            requires_lme=True,
            icd10_codes=["E10.9"],
            required_documents=docs_ceaf,
            prescription_validity_days=90,
            source_id="REME_DF_2024",
            source_page=64,
            notes="Análogo de insulina de ação prolongada (REME-DF / CEAF). Exige LME e laudo de hemoglobina glicada para Diabetes Tipo 1.",
        ),
    ]
    return raw_items


def _build_normative_chunks() -> list[NormativeChunk]:
    """Constrói os chunks normativos (Silver) com metadados de portarias e protocolos oficiais."""
    return [
        NormativeChunk.create(
            chunk_id="CHK-PFPB-001",
            source_id="PFPB_2024",
            document_title="Portaria GM/MS nº 3.677/2024 — Programa Farmácia Popular do Brasil",
            section="Art. 5º — Elenco de Gratuidade Plena (Hipertensão e Diabetes)",
            page_number=11,
            text=(
                "Os medicamentos destinados ao tratamento de hipertensão arterial (losartana potássica 50 mg, "
                "maleato de enalapril 10 mg, atenolol 25 mg, hidroclorotiazida 25 mg, besilato de anlodipino 5 mg) "
                "e diabetes mellitus (cloridrato de metformina 500 mg e 850 mg, glibenclamida 5 mg, insulina humana NPH 100 UI/mL "
                "e insulina humana regular) são dispensados com 100% de gratuidade nas drogarias privadas credenciadas ao "
                "Programa Farmácia Popular do Brasil (Aqui Tem Farmácia Popular). Para retirada, o paciente deve apresentar "
                "documento oficial com foto e número do CPF, acompanhado de receita médica válida emitida por médico do SUS "
                "ou particular, com validade de até 180 dias para uso contínuo."
            ),
            dcb_mentions=[
                "losartana potássica",
                "maleato de enalapril",
                "atenolol",
                "hidroclorotiazida",
                "besilato de anlodipino",
                "cloridrato de metformina",
                "glibenclamida",
                "insulina humana nph",
            ],
            route_category="FARMACIA_POPULAR",
        ),
        NormativeChunk.create(
            chunk_id="CHK-PFPB-002",
            source_id="PFPB_2024",
            document_title="Portaria GM/MS nº 3.677/2024 — Gratuidade Expandida no Farmácia Popular",
            section="Art. 7º — Asma, Osteoporose, Dislipidemia e Diabetes Associada a Doença Cardiovascular",
            page_number=16,
            text=(
                "Passam a contar com 100% de gratuidade no Programa Farmácia Popular do Brasil os medicamentos para asma "
                "(sulfato de salbutamol 100 mcg/dose, dipropionato de beclometasona), osteoporose (alendronato de sódio 70 mg), "
                "dislipidemia/colesterol alto (sinvastatina 10 mg, 20 mg e 40 mg) e dapagliflozina 10 mg. A retirada ocorre "
                "diretamente em qualquer farmácia comercial credenciada mediante apresentação de CPF do titular e receita médica "
                "com CRM, assinatura, endereço do estabelecimento ou paciente e data de emissão inferior a 180 dias."
            ),
            dcb_mentions=[
                "sulfato de salbutamol",
                "alendronato de sódio",
                "sinvastatina",
                "dapagliflozina",
            ],
            route_category="FARMACIA_POPULAR",
        ),
        NormativeChunk.create(
            chunk_id="CHK-RENAME-001",
            source_id="RENAME_2024",
            document_title="RENAME 2024 — Portaria GM/MS nº 6.324/2024 (2ª Edição)",
            section="Anexo I — Componente Básico da Assistência Farmacêutica (Atenção Primária / UBS)",
            page_number=44,
            text=(
                "O Componente Básico da Assistência Farmacêutica (CBAF) compreende os medicamentos essenciais dispensados nas "
                "farmácias das Unidades Básicas de Saúde (UBS), incluindo omeprazol 20 mg cápsula, levotiroxina sódica 25 mcg, "
                "50 mcg e 100 mcg comprimido, amoxicilina 500 mg cápsula, dipirona sódica 500 mg e paracetamol 500 mg. "
                "Estes itens não integram a rede privada do Farmácia Popular e devem ser retirados gratuitamente na UBS de "
                "referência da Região Administrativa do cidadão, apresentando Cartão Nacional de Saúde (CNS), CPF e receita válida."
            ),
            dcb_mentions=[
                "omeprazol",
                "levotiroxina sódica",
                "amoxicilina",
            ],
            route_category="UBS_ATENCAO_PRIMARIA",
        ),
        NormativeChunk.create(
            chunk_id="CHK-REMEDF-001",
            source_id="REME_DF_2024",
            document_title="REME-DF 2024 — Relação de Medicamentos Essenciais da SES-DF",
            section="Capítulo 2 — Dispensação de Controle Especial e Antimicrobianos nas UBS do DF",
            page_number=29,
            text=(
                "Nas Unidades Básicas de Saúde (UBS) da Secretaria de Saúde do Distrito Federal (Ceilândia, Taguatinga, Samambaia, "
                "Gama, Plano Piloto e demais Regiões Administrativas), medicamentos sujeitos a controle especial da Portaria SVS/MS "
                "nº 344/1998, como cloridrato de fluoxetina 20 mg e carbamazepina 200 mg, exigem Receita de Controle Especial em "
                "duas vias com validade de 30 dias a contar da data de emissão, ficando a 1ª via retida na farmácia da UBS. "
                "Para antimicrobianos como amoxicilina 500 mg, a receita tem validade estrita de 10 dias."
            ),
            dcb_mentions=[
                "cloridrato de fluoxetina",
                "carbamazepina",
                "amoxicilina",
            ],
            route_category="UBS_ATENCAO_PRIMARIA",
        ),
        NormativeChunk.create(
            chunk_id="CHK-RENAME-002",
            source_id="RENAME_2024",
            document_title="RENAME 2024 — Portaria GM/MS nº 6.324/2024 (2ª Edição)",
            section="Anexo III — Componente Especializado da Assistência Farmacêutica (CEAF / Alto Custo)",
            page_number=112,
            text=(
                "O Componente Especializado da Assistência Farmacêutica (CEAF) garante o acesso gratuito a medicamentos de alto "
                "custo e alta complexidade definidos em Protocolos Clínicos e Diretrizes Terapêuticas (PCDT), tais como "
                "adalimumabe 40 mg (artrite reumatoide CID M05/M06, espondilite anquilosante CID M45, doença de Crohn CID K50), "
                "atorvastatina cálcica 40 mg (dislipidemia grave CID E78), sacubitril valsartana sódica hidratada 97/103 mg "
                "(insuficiência cardíaca CID I50.0), fumarato de formoterol di-hidratado + budesonida 12/400 mcg (asma grave CID J45) "
                "e hemifumarato de quetiapina 25 mg (esquizofrenia CID F20 e transtorno afetivo bipolar CID F31)."
            ),
            dcb_mentions=[
                "adalimumabe",
                "atorvastatina cálcica",
                "sacubitril valsartana sódica hidratada",
                "fumarato de formoterol di-hidratado + budesonida",
                "hemifumarato de quetiapina",
            ],
            route_category="ALTO_CUSTO_CEAF",
        ),
        NormativeChunk.create(
            chunk_id="CHK-REMEDF-002",
            source_id="REME_DF_2024",
            document_title="Manual do Componente Especializado (Farmácia de Alto Custo) — SES-DF",
            section="Seção 3 — Abertura e Renovação de Processo com LME nas Unidades do DF",
            page_number=64,
            text=(
                "No Distrito Federal, a retirada de medicamentos do Componente Especializado e elenco complementar SES-DF "
                "(incluindo adalimumabe 40 mg, sacubitril valsartana, atorvastatina cálcica 40 mg e insulina glargina 100 UI/mL) "
                "é realizada nas três unidades da Farmácia de Alto Custo (CEAF-DF): Estação 102 Sul do Metrô (Asa Sul), "
                "Ceilândia (EQNN 18/20) e Gama (Praça 1, Setor Leste). O paciente ou cuidador deve apresentar: "
                "1) Laudo para Solicitação, Avaliação e Autorização de Medicamentos (LME) preenchido com CID-10 e válido por 90 dias; "
                "2) Receita médica em duas vias pelo nome genérico (DCB); 3) Exames obrigatórios do PCDT; "
                "4) Documento com foto, CPF, Cartão SUS (CNS) e comprovante de residência no DF."
            ),
            dcb_mentions=[
                "adalimumabe",
                "sacubitril valsartana sódica hidratada",
                "atorvastatina cálcica",
                "insulina glargina",
            ],
            route_category="ALTO_CUSTO_CEAF",
        ),
        NormativeChunk.create(
            chunk_id="CHK-SISREG-001",
            source_id="SISREG_CPPAS_DF",
            document_title="Protocolos de Regulação Ambulatorial SES-DF — SISREG III / CPPAS",
            section="Capítulo 4 — Cardiologia e Exames Cardiovasculares (Ecocardiograma Transtorácico)",
            page_number=21,
            text=(
                "O acesso a exames especializados como Ecocardiograma Transtorácico, Teste Ergométrico e Holter 24h, bem como "
                "consulta especializada em Cardiologia na rede pública do Distrito Federal, ocorre exclusivamente via regulação "
                "pelo sistema SISREG III a partir da Unidade Básica de Saúde (UBS) da Região Administrativa do paciente. "
                "Requisitos obrigatórios de inserção no SISREG: pedido médico fundamentado com hipótese diagnóstica (CID-10), "
                "descrição de sinais de alarme (dispneia, sopro, suspeita de insuficiência cardíaca ou fração de ejeção reduzida), "
                "eletrocardiograma (ECG) prévio anexado e Cartão SUS (CNS) atualizado na UBS."
            ),
            dcb_mentions=[],
            route_category="SISREG_EXAME_CONSULTA",
        ),
        NormativeChunk.create(
            chunk_id="CHK-SISREG-002",
            source_id="SISREG_CPPAS_DF",
            document_title="Protocolos de Regulação Ambulatorial SES-DF — SISREG III / CPPAS",
            section="Capítulo 7 — Endoscopia Digestiva Alta, Ressonância Magnética e Reumatologia/Endocrinologia",
            page_number=38,
            text=(
                "Para agendamento de Endoscopia Digestiva Alta (EDA), Ressonância Magnética ou consultas especializadas em "
                "Reumatologia e Endocrinologia no SUS-DF (SISREG III / Panorama Regulação), o paciente deve comparecer à "
                "sala de regulação/acolhimento da sua UBS com o encaminhamento médico contendo justificativa clínica detalhada "
                "para classificação de prioridade (Prioridade 1 - Vermelha, Prioridade 2 - Amarela, Prioridade 3 - Verde), "
                "resultados de exames laboratoriais básicos (ex.: TSH/T4 livre para endocrinologia; VHS/PCR/Fator Reumatoide "
                "para reumatologia), documento com CPF, Cartão SUS (CNS) e telefone atualizado para aviso de marcação."
            ),
            dcb_mentions=[],
            route_category="SISREG_EXAME_CONSULTA",
        ),
        NormativeChunk.create(
            chunk_id="CHK-VALIDADE-001",
            source_id="RENAME_2024",
            document_title="Guia de Gestão de Validade de Receitas e Renovação Contínua no SUS",
            section="Regras Gerais de Vigência e Alertas Preventivos (Carteira Digital RF08)",
            page_number=89,
            text=(
                "As receitas de medicamentos de uso contínuo (hipertensão, diabetes, dislipidemia, asma, hipotireoidismo) "
                "possuem validade de 180 dias (6 meses) na Farmácia Popular e nas UBS, exceto anticoncepcionais (365 dias), "
                "psicotrópicos da Portaria 344/98 (30 dias) e antimicrobianos (10 dias). Processos do Componente Especializado "
                "(LME na Farmácia de Alto Custo) possuem vigência trimestral (90 dias), exigindo renovação preventiva com "
                "antecedência de 15 e 7 dias antes do vencimento para evitar interrupção do tratamento."
            ),
            dcb_mentions=[],
            route_category="GERAL",
        ),
    ]


class DataSynchronizer:
    """Sincroniza ou materializa os dados Silver/Gold e gera o manifesto SHA-256."""

    def __init__(self, paths: ProjectPaths) -> None:
        self.paths = paths
        self.paths.ensure_dirs()

    def sync(self, engineering_dir: Path | None = None) -> DataManifest:
        """Sincroniza artefatos de `engineering_dir` (se disponível) ou materializa a base canônica."""
        engineering_source = "canonical_materialization_v2024.2"

        if engineering_dir is not None and engineering_dir.exists():
            eng_gold = engineering_dir / "data" / "gold" / "medicamentos_sus_canonical.json"
            eng_silver = engineering_dir / "data" / "silver" / "normative_chunks.json"
            if eng_gold.exists() and eng_silver.exists():
                shutil.copy2(eng_gold, self.paths.gold_dir / "medicamentos_sus_canonical.json")
                shutil.copy2(eng_silver, self.paths.silver_dir / "normative_chunks.json")
                engineering_source = f"imported_from:{engineering_dir.resolve()}"

        gold_path = self.paths.gold_dir / "medicamentos_sus_canonical.json"
        silver_path = self.paths.silver_dir / "normative_chunks.json"

        if not gold_path.exists() or not silver_path.exists():
            meds = _build_canonical_medications()
            chunks = _build_normative_chunks()
            gold_payload = [m.to_dict() for m in meds]
            silver_payload = [c.to_dict() for c in chunks]
            gold_path.write_text(
                json.dumps(gold_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            silver_path.write_text(
                json.dumps(silver_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        gold_raw = gold_path.read_text(encoding="utf-8")
        silver_raw = silver_path.read_text(encoding="utf-8")
        gold_items = json.loads(gold_raw)
        silver_items = json.loads(silver_raw)

        gold_sha = compute_sha256(gold_raw)
        silver_sha = compute_sha256(silver_raw)
        combined_sha = compute_sha256(f"{gold_sha}:{silver_sha}")

        manifest = DataManifest(
            manifest_version="2024.2.0",
            generated_at_utc=datetime.now(UTC).isoformat(),
            engineering_source=engineering_source,
            canonical_medications_sha256=gold_sha,
            normative_chunks_sha256=silver_sha,
            combined_sha256=combined_sha,
            record_counts={
                "canonical_medications": len(gold_items),
                "normative_chunks": len(silver_items),
            },
        )
        manifest_path = self.paths.manifests_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return manifest

    def load_medications(self) -> list[CanonicalMedication]:
        """Carrega a camada Gold de medicamentos canônicos."""
        gold_path = self.paths.gold_dir / "medicamentos_sus_canonical.json"
        if not gold_path.exists():
            self.sync()
        raw_list = json.loads(gold_path.read_text(encoding="utf-8"))
        return [CanonicalMedication.from_dict(item) for item in raw_list]

    def load_chunks(self) -> list[NormativeChunk]:
        """Carrega a camada Silver de chunks normativos."""
        silver_path = self.paths.silver_dir / "normative_chunks.json"
        if not silver_path.exists():
            self.sync()
        raw_list = json.loads(silver_path.read_text(encoding="utf-8"))
        return [NormativeChunk.from_dict(item) for item in raw_list]

    def load_manifest(self) -> DataManifest:
        """Carrega o manifesto de linhagem SHA-256."""
        manifest_path = self.paths.manifests_dir / "manifest.json"
        if not manifest_path.exists():
            return self.sync()
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        return DataManifest(
            manifest_version=str(raw["manifest_version"]),
            generated_at_utc=str(raw["generated_at_utc"]),
            engineering_source=str(raw["engineering_source"]),
            canonical_medications_sha256=str(raw["canonical_medications_sha256"]),
            normative_chunks_sha256=str(raw["normative_chunks_sha256"]),
            combined_sha256=str(raw["combined_sha256"]),
            record_counts={str(k): int(v) for k, v in raw["record_counts"].items()},
        )

