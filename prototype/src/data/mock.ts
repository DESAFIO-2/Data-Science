// Dados de exemplo (mock) usados pelas telas enquanto não há backend.

export const usuario = {
  nome: 'Maria Helena',
  nomeCompleto: 'Maria Helena Duarte Souza',
  cpf: '123.456.789-09',
  nascimento: '12/03/1958',
  celular: '(61) 99876-5432',
  email: 'maria.helena@email.com',
  cns: '742 8819 0041 2309',
  ubs: 'UBS 1 - Asa Sul',
  cidade: 'Brasília, DF',
};

export type DoseStatus = 'tomada' | 'atrasada' | 'aguardando' | 'noturno';

export type Medicamento = {
  id: string;
  nome: string;
  dose: string;
  forma: string;
  horario: string;
  categoria: string;
  grupo: 'priority' | 'continuous';
  icone: string;
  instrucao: string;
  estoque: { restante: number; total: number; unidade: string; diasReposicao?: number };
};

export const medicamentos: Medicamento[] = [
  {
    id: 'losartana',
    nome: 'Losartana Potássica',
    dose: '50mg',
    forma: 'Comprimido',
    horario: '08:00',
    categoria: 'Cardiovascular',
    grupo: 'continuous',
    icone: 'cardiology',
    instrucao: 'Manhã, em jejum',
    estoque: { restante: 18, total: 56, unidade: 'comprimidos', diasReposicao: 6 },
  },
  {
    id: 'metformina',
    nome: 'Metformina Cloridrato',
    dose: '850mg',
    forma: 'Comprimido Revestido',
    horario: '12:30',
    categoria: 'Metabolismo',
    grupo: 'priority',
    icone: 'pill',
    instrucao: 'Tomar com 200ml de água após o almoço',
    estoque: { restante: 40, total: 60, unidade: 'comprimidos' },
  },
  {
    id: 'sinvastatina',
    nome: 'Sinvastatina',
    dose: '20mg',
    forma: 'Comprimido',
    horario: '19:00',
    categoria: 'Lipídios',
    grupo: 'continuous',
    icone: 'water_drop',
    instrucao: 'Programado para o término do jantar',
    estoque: { restante: 26, total: 30, unidade: 'comprimidos' },
  },
  {
    id: 'insulina',
    nome: 'Insulina Humana NPH',
    dose: '18 UI',
    forma: '100 UI/mL • Caneta Recarregável',
    horario: '22:00',
    categoria: 'Injetável',
    grupo: 'priority',
    icone: 'vaccines',
    instrucao: 'Conservar entre 2°C e 8°C',
    estoque: { restante: 64, total: 300, unidade: 'UI' },
  },
];

export const agenda = [
  {
    id: 'c1',
    tipo: 'consulta' as const,
    diaSemana: 'QUI',
    dia: '14',
    mes: 'NOV',
    hora: '14:20',
    especialidade: 'Clínica Geral',
    titulo: 'Dr. Roberto Mendes',
    local: 'UBS 1 - Asa Sul • Consultório 4',
  },
  {
    id: 'e1',
    tipo: 'exame' as const,
    diaSemana: 'SEX',
    dia: '15',
    mes: 'NOV',
    hora: '07:00',
    especialidade: 'Coleta de Sangue',
    titulo: 'Perfil Lipídico & Hemoglobina Glicada',
    local: 'Protocolo: Jejum estrito de 8 horas',
  },
];

export type Farmacia = {
  id: string;
  nome: string;
  endereco: string;
  distancia: string;
  tempo: string;
  selo: string;
  seloTone: 'success' | 'warning';
  estoque: { texto: string; destaque?: string; alerta?: boolean; icone: string };
  telefone: string;
};

export const farmacias: Farmacia[] = [
  {
    id: 'f1',
    nome: 'Drogaria São Paulo',
    endereco: 'CLS 106 Bloco A, Loja 12 • Asa Sul',
    distancia: '180m',
    tempo: '4 min a pé',
    selo: 'SUS 100% Gratuito',
    seloTone: 'success',
    estoque: { texto: 'Losartana Potássica 50mg — ', destaque: '142 caixas disponíveis', icone: 'inventory_2' },
    telefone: '6133450000',
  },
  {
    id: 'f2',
    nome: 'Drogasil',
    endereco: 'CLN 302 Bloco B, Comércio Local • Asa Norte',
    distancia: '450m',
    tempo: '7 min a pé',
    selo: 'Remédio Disponível',
    seloTone: 'success',
    estoque: { texto: 'Estoque regularizado • Atendimento prioritário', icone: 'check_circle' },
    telefone: '6133460000',
  },
  {
    id: 'f3',
    nome: 'Pague Menos',
    endereco: 'SQS 214 Bloco K • Asa Sul',
    distancia: '820m',
    tempo: '12 min a pé',
    selo: 'Estoque Baixo',
    seloTone: 'warning',
    estoque: { texto: 'Atenção: Apenas ', destaque: '2 caixas restantes', alerta: true, icone: 'warning' },
    telefone: '6133470000',
  },
];

export type Receita = {
  id: string;
  medicamento: string;
  posologia: string;
  medico: string;
  crm: string;
  emitida: string;
  validade: string;
  diasRestantes: number;
  diasTotais: number;
  tipo: 'Uso Contínuo' | 'Controle Especial' | 'Simples';
  status: 'ativa' | 'vencendo' | 'vencida';
  codigo: string;
};

export const receitas: Receita[] = [
  {
    id: 'r1',
    medicamento: 'Losartana Potássica 50mg',
    posologia: '1 comprimido pela manhã',
    medico: 'Dr. Roberto Mendes',
    crm: 'CRM-DF 12345',
    emitida: '13/05/2026',
    validade: '13/11/2026',
    diasRestantes: 7,
    diasTotais: 180,
    tipo: 'Uso Contínuo',
    status: 'vencendo',
    codigo: 'SUS-DF-2026-0048213',
  },
  {
    id: 'r2',
    medicamento: 'Metformina Cloridrato 850mg',
    posologia: '1 comprimido após o almoço',
    medico: 'Dr. Roberto Mendes',
    crm: 'CRM-DF 12345',
    emitida: '02/09/2026',
    validade: '01/03/2027',
    diasRestantes: 115,
    diasTotais: 180,
    tipo: 'Uso Contínuo',
    status: 'ativa',
    codigo: 'SUS-DF-2026-0071542',
  },
  {
    id: 'r3',
    medicamento: 'Insulina Humana NPH 100 UI/mL',
    posologia: '18 UI às 22:00, via subcutânea',
    medico: 'Dra. Ana Paula Lima',
    crm: 'CRM-DF 67890',
    emitida: '20/08/2026',
    validade: '16/02/2027',
    diasRestantes: 102,
    diasTotais: 180,
    tipo: 'Uso Contínuo',
    status: 'ativa',
    codigo: 'SUS-DF-2026-0069907',
  },
  {
    id: 'r4',
    medicamento: 'Sinvastatina 20mg',
    posologia: '1 comprimido após o jantar',
    medico: 'Dr. Roberto Mendes',
    crm: 'CRM-DF 12345',
    emitida: '10/10/2026',
    validade: '08/04/2027',
    diasRestantes: 153,
    diasTotais: 180,
    tipo: 'Uso Contínuo',
    status: 'ativa',
    codigo: 'SUS-DF-2026-0082210',
  },
  {
    id: 'r5',
    medicamento: 'Amoxicilina 500mg',
    posologia: '1 cápsula de 8 em 8 horas por 7 dias',
    medico: 'Dra. Ana Paula Lima',
    crm: 'CRM-DF 67890',
    emitida: '04/06/2026',
    validade: '14/06/2026',
    diasRestantes: 0,
    diasTotais: 10,
    tipo: 'Controle Especial',
    status: 'vencida',
    codigo: 'SUS-DF-2026-0051120',
  },
];

export type Notificacao = {
  id: string;
  icone: string;
  tone: 'danger' | 'warning' | 'success' | 'info';
  titulo: string;
  texto: string;
  quando: string;
  lida: boolean;
};

export const notificacoes: Notificacao[] = [
  {
    id: 'n1',
    icone: 'alarm',
    tone: 'danger',
    titulo: 'Dose atrasada: Metformina 850mg',
    texto: 'O horário das 12:30 passou. Confirme se já tomou.',
    quando: 'Agora',
    lida: false,
  },
  {
    id: 'n2',
    icone: 'prescriptions',
    tone: 'warning',
    titulo: 'Receita da Losartana vence em 7 dias',
    texto: 'Peça a renovação na UBS 1 - Asa Sul para não ficar sem o remédio.',
    quando: 'Hoje, 08:00',
    lida: false,
  },
  {
    id: 'n3',
    icone: 'event',
    tone: 'info',
    titulo: 'Consulta confirmada',
    texto: 'Clínica Geral com Dr. Roberto Mendes, quinta-feira (14/11) às 14:20.',
    quando: 'Ontem',
    lida: true,
  },
  {
    id: 'n4',
    icone: 'local_shipping',
    tone: 'success',
    titulo: 'Remédio em Casa saiu para entrega',
    texto: 'Sinvastatina 20mg (2 caixas) chega até sexta-feira.',
    quando: 'Ontem',
    lida: true,
  },
];
