import { Platform } from 'react-native';

export interface HealthResponse {
  status: string;
  service: string;
  embedding_profile?: Record<string, unknown>;
  chroma_collections?: Record<string, number | string>;
  stt_provider_configured?: boolean;
  tts_voice?: string;
}

export interface AuditedMedicationDTO {
  dcb_name: string;
  concentration: string;
  rename_component: string;
  dispensation_route: string;
  requires_lme: boolean;
  validity_days: number;
  where_to_collect: string;
  required_documents: string[];
  source_citation: string;
}

export interface SisregGuidanceDTO {
  procedure_name: string;
  regulation_channel: string;
  required_documents: string[];
  priority_rule: string;
  source_citation: string;
  preparation_tips: string[];
}

export interface RetrievedChunkDTO {
  chunk_id: string;
  score: number;
  source_id: string;
  document_title: string;
  section: string;
  page_number: number;
  route_category: string;
  text: string;
  matched_dcb?: string | null;
  retriever_name?: string;
}

export interface ConversationTurnResponse {
  session_id: string;
  turn_count: number;
  transcript: string;
  stt_provider: string;
  primary_route: string;
  sanitized_query: string;
  detected_ra: string;
  is_clinical_block: boolean;
  abstained: boolean;
  synthesized_guidance: string;
  spoken_guidance: string;
  follow_up_suggestions: string[];
  preparation_tips: string[];
  checklist_documents: string[];
  validity_alerts: string[];
  citations: string[];
  audited_medications: AuditedMedicationDTO[];
  sisreg_guidance: SisregGuidanceDTO[];
  retrieved_chunks: RetrievedChunkDTO[];
  remembered_history: string[];
  agent_trace: string[];
  tts_audio_base64: string | null;
  tts_mime_type: string;
  tts_provider: string;
  tts_voice: string;
  tts_fallback_reason?: string | null;
}

export interface SessionStateResponse {
  session_id: string;
  detected_ra: string;
  known_medications: string[];
  known_exams: string[];
  sanitized_history: string[];
  turn_count: number;
}

export interface AutocompleteMedicationItem {
  medication_id: string;
  dcb_principio_ativo: string;
  concentracao: string;
  forma_farmaceutica: string;
  via_retirada: string;
  dispensacao_gratuita_prevista: boolean;
  exige_lme: boolean;
  texto_exibicao: string;
}

export interface AutocompleteResponse {
  consulta: string;
  total_encontrados: number;
  resultados: AutocompleteMedicationItem[];
}

export interface PrescriptionItemInput {
  nome_digitado: string;
  principio_ativo_dcb?: string;
  concentracao?: string;
  forma_farmaceutica?: string;
  posologia?: string;
  quantidade_prescrita?: string;
}

export interface PrescriptionAuditRequestDTO {
  itens: PrescriptionItemInput[];
  data_emissao?: string;
  regiao_administrativa: string;
  tipo_prescritor?: string;
  pergunta_adicional?: string;
}

export interface ItemRoteiroDTO {
  medicamento: string;
  principio_ativo_dcb: string;
  via_retirada: string;
  local_sugerido: string;
  o_que_levar: string[];
  dias_validade_receita: number | null;
  data_limite_validade: string | null;
  dias_restantes: number | null;
  alerta_vencimento_proximo: boolean;
  citacao_normativa: string;
}

export interface PrescriptionAuditResponseDTO {
  sucesso: boolean;
  regiao_administrativa: string;
  itens: ItemRoteiroDTO[];
  resumo_acolhedor: string;
  aviso_preservacao_ato_medico: string;
  solicitou_automedicacao: boolean;
}

export interface NearbyPharmacyDTO {
  cnes: string;
  name: string;
  address: string;
  neighborhood_or_ra: string;
  pharmacy_type: string;
  latitude: number | null;
  longitude: number | null;
  google_maps_url?: string;
  covered_ras?: string[] | null;
  distance_km?: number;
}

export interface NearbyPharmaciesResponse {
  ra: string;
  total: number;
  items: NearbyPharmacyDTO[];
}

export interface CeafStockItemDTO {
  cod_produto?: string;
  desc_produto?: string;
  medicamento?: string;
  unidade?: string;
  disp_estoque?: string | number;
  origem_abastecimento?: string;
  psicotropico?: string;
  ultima_atualizacao?: string;
}

export interface CeafStockResponse {
  query: string;
  unidade: string;
  updated_at?: string | null;
  total: number;
  items: CeafStockItemDTO[];
}

export function getDefaultApiBaseUrl(): string {
  const envUrl = process.env.EXPO_PUBLIC_API_URL?.trim();
  if (envUrl) return envUrl.replace(/\/+$/, '');
  if (Platform.OS === 'web' && typeof window !== 'undefined') {
    const host = window.location.hostname || '127.0.0.1';
    return `http://${host}:8000`;
  }
  return 'http://127.0.0.1:8000';
}

function resolveUrl(path: string, baseUrl?: string): string {
  const cleanBase = (baseUrl?.trim() || getDefaultApiBaseUrl()).replace(/\/+$/, '');
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return `${cleanBase}${cleanPath}`;
}

async function requestJson<T>(path: string, init?: RequestInit, baseUrl?: string, timeoutMs = 20000): Promise<T> {
  const url = resolveUrl(path, baseUrl);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      ...init,
      signal: controller.signal,
    });
    if (!res.ok) {
      let detail = `Erro HTTP ${res.status}`;
      try {
        const errJson = (await res.json()) as { detail?: string };
        if (errJson.detail) detail = errJson.detail;
      } catch {
        // Ignora corpo não-JSON em erro HTTP.
      }
      throw new Error(detail);
    }
    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') {
      throw new Error(`Tempo esgotado ao aguardar o servidor Multiagentes (${url}).`);
    }
    if (err instanceof TypeError) {
      throw new Error(
        `Servidor Multiagentes inacessível em ${url}. Inicie a API com "make serve" no backend.`,
      );
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

export async function checkHealth(baseUrl?: string): Promise<HealthResponse> {
  return requestJson<HealthResponse>('/health', { method: 'GET' }, baseUrl, 5000);
}

export async function sendChatTurn(
  payload: {
    text: string;
    session_id?: string | null;
    days_since_emission?: number;
    include_audio?: boolean;
  },
  baseUrl?: string,
): Promise<ConversationTurnResponse> {
  return requestJson<ConversationTurnResponse>(
    '/v1/chat',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: payload.text,
        session_id: payload.session_id ?? null,
        days_since_emission: payload.days_since_emission ?? 166,
        include_audio: payload.include_audio ?? false,
      }),
    },
    baseUrl,
  );
}

export async function sendVoiceTurn(
  params: {
    text?: string | null;
    audioBlob?: Blob | null;
    audioUri?: string | null;
    audioName?: string;
    audioMimeType?: string;
    session_id?: string | null;
    days_since_emission?: number;
    synthesize_audio?: boolean;
  },
  baseUrl?: string,
): Promise<ConversationTurnResponse> {
  const form = new FormData();
  if (params.text?.trim()) {
    form.append('text', params.text.trim());
  }
  if (params.audioBlob) {
    form.append('audio', params.audioBlob, params.audioName ?? 'zelo_voz.webm');
  } else if (params.audioUri) {
    form.append('audio', {
      uri: params.audioUri,
      name: params.audioName ?? 'zelo_voz.m4a',
      type: params.audioMimeType ?? 'audio/m4a',
    } as unknown as Blob);
  }
  if (params.session_id) {
    form.append('session_id', params.session_id);
  }
  form.append('days_since_emission', String(params.days_since_emission ?? 166));
  form.append('synthesize_audio', String(params.synthesize_audio ?? true));

  return requestJson<ConversationTurnResponse>(
    '/v1/voice-turn',
    {
      method: 'POST',
      body: form,
    },
    baseUrl,
    30000,
  );
}

export async function clearSession(sessionId: string, baseUrl?: string): Promise<void> {
  await requestJson<{ status: string }>(
    `/v1/sessions/${encodeURIComponent(sessionId)}`,
    { method: 'DELETE' },
    baseUrl,
  );
}

export async function fetchSession(sessionId: string, baseUrl?: string): Promise<SessionStateResponse> {
  return requestJson<SessionStateResponse>(
    `/v1/sessions/${encodeURIComponent(sessionId)}`,
    { method: 'GET' },
    baseUrl,
  );
}

export async function autocompleteMedications(
  q: string,
  limite = 10,
  baseUrl?: string,
): Promise<AutocompleteResponse> {
  const qs = new URLSearchParams({ q, limite: String(limite) });
  return requestJson<AutocompleteResponse>(
    `/api/v1/medications/autocomplete?${qs.toString()}`,
    { method: 'GET' },
    baseUrl,
  );
}

export async function auditPrescription(
  payload: PrescriptionAuditRequestDTO,
  baseUrl?: string,
): Promise<PrescriptionAuditResponseDTO> {
  return requestJson<PrescriptionAuditResponseDTO>(
    '/api/v1/prescriptions/audit',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
    baseUrl,
  );
}

export async function fetchNearbyPharmacies(
  params: { ra?: string; q?: string; lat?: number; lng?: number; limite?: number },
  baseUrl?: string,
): Promise<NearbyPharmaciesResponse> {
  const qs = new URLSearchParams();
  if (params.ra) qs.set('ra', params.ra);
  if (params.q) qs.set('q', params.q);
  if (params.lat !== undefined) qs.set('lat', String(params.lat));
  if (params.lng !== undefined) qs.set('lng', String(params.lng));
  qs.set('limite', String(params.limite ?? 8));
  return requestJson<NearbyPharmaciesResponse>(`/v1/pharmacies/nearby?${qs.toString()}`, { method: 'GET' }, baseUrl);
}

export async function fetchCeafStock(
  params: { q?: string; unidade?: string; limite?: number },
  baseUrl?: string,
): Promise<CeafStockResponse> {
  const qs = new URLSearchParams();
  if (params.q) qs.set('q', params.q);
  if (params.unidade) qs.set('unidade', params.unidade);
  qs.set('limite', String(params.limite ?? 15));
  return requestJson<CeafStockResponse>(`/v1/ceaf-stock?${qs.toString()}`, { method: 'GET' }, baseUrl);
}

