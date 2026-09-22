export type Band = "Normal" | "Watch" | "Priority" | "Critical";
export type Role = "supervisor" | "inspector" | "officer";
export type ScreenId = "yard" | "queue" | "stack" | "nodes" | "season" | "settings";

export interface StackSummary {
  stack_id: string;
  row_id: string;
  position_index: number;
  tonnage_mt: number;
  age_days: number;
  assigned_scenario: string;
  is_evacuated: boolean;
  blocks_stack_id: string | null;
  blocked_by_stack_id: string | null;
  current_epi: number;
  band: Band | string;
  m_est: number;
  aw_max: number;
  t_core: number;
  dm_dt_24h: number;
  n_ok: number;
  qflag: string;
  needs_inspection: boolean;
  vulnerability_score: number;
  active_branch: string;
  override_fired: boolean;
}

export interface YardOverview {
  yard_id: string;
  sim_time: string;
  is_clock_running: boolean;
  speed_multiplier: number;
  weather_mode: string;
  weather_stale: boolean;
  ambient_temp: number;
  ambient_rh: number;
  is_raining: boolean;
  r72_mm: number;
  p_rain: number;
  stacks_count: number;
  at_risk_count: number;
  stacks: StackSummary[];
}

export interface QueueItem {
  loading_order: number;
  truck_number: number;
  stack_id: string;
  tonnage_mt: number;
  epi_score: number;
  band: Band | string;
  hours_to_breach: number | null;
  reason_en: string;
  reason_ta: string;
  is_blocked: boolean;
  blocked_by: string | null;
  blocks: string | null;
  is_overridden: boolean;
  override_reason_code: string | null;
}

export interface DispatchPlan {
  timestamp: string;
  allocated_capacity_mt: number;
  total_loaded_mt: number;
  capacity_fill_fraction: number;
  queue: QueueItem[];
  greedy_protected_tonne_epi: number;
  optimized_protected_tonne_epi: number;
  optimization_improvement_gain: number;
  supervisor_overrides_count: number;
}

export interface NodeDetail {
  node_id: string;
  stack_id: string;
  position: string;
  health_state: string;
  battery_voltage: number;
  erh_observed: number;
  temp_observed: number;
  temp_core_observed: number;
  is_suspect: boolean;
  is_stale: boolean;
  suspect_reasons: string[];
}

export interface VulnerabilityRubric {
  tarpaulin_condition: number;
  dunnage_plinth: number;
  drainage_proximity: number;
  position_in_row: number;
  residence_time: number;
}

export interface StackDetail {
  summary: StackSummary;
  rubric: VulnerabilityRubric;
  nodes: NodeDetail[];
  recent_history: Array<Record<string, unknown>>;
  sub_index_breakdown: Record<string, number>;
}

export interface SeasonReport {
  total_tonnes_evacuated: number;
  tonnes_by_band: Record<string, number>;
  avoided_breaches_count: number;
  average_lead_time_hours: number;
  node_survival_rate_percent: number;
  optimization_improvement_gain: number;
  precision_at_6: number;
  evacuated_stacks: Array<Record<string, unknown>>;
}

export interface ActiveAlert {
  alert_id: string;
  stack_id: string;
  band: string;
  triggered_at: string;
  dwell_satisfied: boolean;
  reason_en: string;
  reason_ta: string;
  driving_node_ids: string[];
  is_active: boolean;
  simulated_sms_sent: boolean;
}

export interface SmsMessage {
  alert_id: string;
  stack_id: string;
  band: string;
  timestamp: string;
  sms_body_ta: string;
  sms_body_en: string;
  recipient: string;
}

export interface AlertsPayload {
  active_alerts: ActiveAlert[];
  total_alerts_count: number;
  simulated_sms_inbox: SmsMessage[];
}

export interface SubIndexWeights {
  w_M: number;
  w_R: number;
  w_T: number;
  w_A: number;
  w_F: number;
  w_V: number;
}

export interface SettingsPayload {
  version_id: number;
  weights: SubIndexWeights;
  anchors: Record<string, number>;
  alert_ladder: Record<string, number>;
  isotherm_parameters: {
    adsorption: { A: number; B: number; C: number };
    desorption: { A: number; B: number; C: number };
  };
  history_versions: Array<Record<string, unknown>>;
}

export interface WsTick {
  event_type: string;
  timestamp: string;
  data: {
    yard?: YardOverview;
    dispatch?: DispatchPlan | null;
    active_alerts_count?: number;
  };
}
