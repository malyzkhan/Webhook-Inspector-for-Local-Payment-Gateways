export type WebhookEvent = {
  id: string;
  endpoint_id: string;
  method: string;
  headers: Record<string, string>;
  query_params: Record<string, unknown>;
  parsed_body: unknown;
  raw_query: string;
  raw_body_base64: string;
  content_type: string;
  client_ip: string | null;
  gateway: "JazzCash" | "EasyPaisa" | "Generic";
  created_at: string;
  response_status: number;
};
