export type Task = 'screening' | 'biomarker';
export type Inputs = Record<string, number | null>;
export type Quality = {feature: string; state: 'observed' | 'imputed' | 'required' | 'invalid' | 'outside' | 'unusual'; message: string};
export type Assessment = {
  status: 'ok'; task: Task; model_version: string; run_id: string; model: string;
  label: string; probability: number; threshold: number; outcome: string;
  calibration: string; explanation_method: string; limitations: string[];
  present: number; total: number; quality: Quality[];
  explanations: {feature: string; observed: number; reference: number; probability_difference: number}[];
} | {status: 'invalid'; errors: string[]; quality: Quality[]; present: number};
