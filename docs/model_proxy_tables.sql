--
-- PostgreSQL database dump
--

\restrict evSFOjdrIB0qsizkOCt4aQuabCDXssCubADIohlohiRmGPedGUcw7cc65e4cxJQ

-- Dumped from database version 17.6
-- Dumped by pg_dump version 17.6 (Debian 17.6-2.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: model_proxy_api_messages; Type: TABLE; Schema: public; Owner: supabase_admin
--

CREATE TABLE public.model_proxy_api_messages (
    id bigint NOT NULL,
    request_id uuid,
    message_index integer,
    role character varying(50),
    content text,
    name character varying(255),
    tool_calls jsonb,
    tool_call_id character varying(255),
    token_count integer,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.model_proxy_api_messages OWNER TO supabase_admin;

--
-- Name: TABLE model_proxy_api_messages; Type: COMMENT; Schema: public; Owner: supabase_admin
--

COMMENT ON TABLE public.model_proxy_api_messages IS 'Stores individual messages from API requests';


--
-- Name: model_proxy_api_messages_id_seq; Type: SEQUENCE; Schema: public; Owner: supabase_admin
--

CREATE SEQUENCE public.model_proxy_api_messages_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.model_proxy_api_messages_id_seq OWNER TO supabase_admin;

--
-- Name: model_proxy_api_messages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: supabase_admin
--

ALTER SEQUENCE public.model_proxy_api_messages_id_seq OWNED BY public.model_proxy_api_messages.id;


--
-- Name: model_proxy_api_requests; Type: TABLE; Schema: public; Owner: supabase_admin
--

CREATE TABLE public.model_proxy_api_requests (
    id bigint NOT NULL,
    "timestamp" timestamp with time zone DEFAULT now(),
    request_id uuid DEFAULT extensions.uuid_generate_v4(),
    app_id character varying(255),
    progress_id integer,
    model character varying(100),
    temperature numeric(3,2),
    max_tokens integer,
    top_p numeric(3,2),
    frequency_penalty numeric(3,2),
    presence_penalty numeric(3,2),
    stream boolean,
    tool_choice text,
    request_payload jsonb,
    response_payload jsonb,
    response_id character varying(255),
    response_model character varying(100),
    completion_tokens integer,
    prompt_tokens integer,
    total_tokens integer,
    request_token_count integer,
    response_token_count integer,
    prompt_cost_usd numeric(10,6),
    completion_cost_usd numeric(10,6),
    total_cost_usd numeric(10,6),
    request_time timestamp with time zone,
    response_time timestamp with time zone,
    duration_ms integer,
    status_code integer,
    error_message text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    provider_name character varying(100),
    user_id character varying(255),
    agent_id character varying(255),
    project_id character varying(255),
    route character varying(255),
    cached_tokens integer DEFAULT 0,
    prompt_char_count integer,
    response_char_count integer,
    prompt_sha256 text,
    message_count integer,
    pricing_tier character varying(50) DEFAULT 'standard'::character varying,
    metadata jsonb DEFAULT '{}'::jsonb,
    total_tokens_computed integer GENERATED ALWAYS AS ((COALESCE(prompt_tokens, 0) + COALESCE(completion_tokens, 0))) STORED
);


ALTER TABLE public.model_proxy_api_requests OWNER TO supabase_admin;

--
-- Name: TABLE model_proxy_api_requests; Type: COMMENT; Schema: public; Owner: supabase_admin
--

COMMENT ON TABLE public.model_proxy_api_requests IS 'Logs all API requests and responses to OpenAI models';


--
-- Name: COLUMN model_proxy_api_requests.provider_name; Type: COMMENT; Schema: public; Owner: supabase_admin
--

COMMENT ON COLUMN public.model_proxy_api_requests.provider_name IS 'Provider name (openai, anthropic, local, etc.)';


--
-- Name: COLUMN model_proxy_api_requests.user_id; Type: COMMENT; Schema: public; Owner: supabase_admin
--

COMMENT ON COLUMN public.model_proxy_api_requests.user_id IS 'User identifier for user-level analytics';


--
-- Name: COLUMN model_proxy_api_requests.agent_id; Type: COMMENT; Schema: public; Owner: supabase_admin
--

COMMENT ON COLUMN public.model_proxy_api_requests.agent_id IS 'Agent identifier';


--
-- Name: COLUMN model_proxy_api_requests.project_id; Type: COMMENT; Schema: public; Owner: supabase_admin
--

COMMENT ON COLUMN public.model_proxy_api_requests.project_id IS 'Project identifier for multi-project tracking';


--
-- Name: COLUMN model_proxy_api_requests.cached_tokens; Type: COMMENT; Schema: public; Owner: supabase_admin
--

COMMENT ON COLUMN public.model_proxy_api_requests.cached_tokens IS 'Cached tokens (prompt caching) - reduces cost';


--
-- Name: COLUMN model_proxy_api_requests.metadata; Type: COMMENT; Schema: public; Owner: supabase_admin
--

COMMENT ON COLUMN public.model_proxy_api_requests.metadata IS 'Freeform JSON metadata (condensation stats, etc.)';


--
-- Name: model_proxy_api_requests_id_seq; Type: SEQUENCE; Schema: public; Owner: supabase_admin
--

CREATE SEQUENCE public.model_proxy_api_requests_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.model_proxy_api_requests_id_seq OWNER TO supabase_admin;

--
-- Name: model_proxy_api_requests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: supabase_admin
--

ALTER SEQUENCE public.model_proxy_api_requests_id_seq OWNED BY public.model_proxy_api_requests.id;


--
-- Name: model_proxy_api_tools; Type: TABLE; Schema: public; Owner: supabase_admin
--

CREATE TABLE public.model_proxy_api_tools (
    id bigint NOT NULL,
    request_id uuid,
    tool_index integer,
    tool_type character varying(50),
    function_name character varying(255),
    function_description text,
    function_parameters jsonb,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.model_proxy_api_tools OWNER TO supabase_admin;

--
-- Name: TABLE model_proxy_api_tools; Type: COMMENT; Schema: public; Owner: supabase_admin
--

COMMENT ON TABLE public.model_proxy_api_tools IS 'Stores tool/function definitions used in requests';


--
-- Name: model_proxy_api_tools_id_seq; Type: SEQUENCE; Schema: public; Owner: supabase_admin
--

CREATE SEQUENCE public.model_proxy_api_tools_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.model_proxy_api_tools_id_seq OWNER TO supabase_admin;

--
-- Name: model_proxy_api_tools_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: supabase_admin
--

ALTER SEQUENCE public.model_proxy_api_tools_id_seq OWNED BY public.model_proxy_api_tools.id;


--
-- Name: model_proxy_cost_summary; Type: VIEW; Schema: public; Owner: supabase_admin
--

CREATE VIEW public.model_proxy_cost_summary AS
 SELECT date("timestamp") AS date,
    model,
    count(*) AS request_count,
    sum(prompt_tokens) AS total_prompt_tokens,
    sum(completion_tokens) AS total_completion_tokens,
    sum(total_tokens) AS total_tokens,
    sum(total_cost_usd) AS total_cost_usd,
    avg(total_cost_usd) AS avg_cost_per_request,
    avg(duration_ms) AS avg_duration_ms
   FROM public.model_proxy_api_requests
  WHERE (status_code = 200)
  GROUP BY (date("timestamp")), model
  ORDER BY (date("timestamp")) DESC, model;


ALTER VIEW public.model_proxy_cost_summary OWNER TO supabase_admin;

--
-- Name: VIEW model_proxy_cost_summary; Type: COMMENT; Schema: public; Owner: supabase_admin
--

COMMENT ON VIEW public.model_proxy_cost_summary IS 'Daily cost summary by model';


--
-- Name: model_proxy_hourly_usage; Type: VIEW; Schema: public; Owner: supabase_admin
--

CREATE VIEW public.model_proxy_hourly_usage AS
 SELECT date_trunc('hour'::text, "timestamp") AS hour,
    model,
    count(*) AS request_count,
    sum(total_tokens) AS total_tokens,
    sum(total_cost_usd) AS total_cost_usd,
    avg(duration_ms) AS avg_duration_ms,
    max(total_cost_usd) AS max_cost_per_request
   FROM public.model_proxy_api_requests
  WHERE (status_code = 200)
  GROUP BY (date_trunc('hour'::text, "timestamp")), model
  ORDER BY (date_trunc('hour'::text, "timestamp")) DESC, model;


ALTER VIEW public.model_proxy_hourly_usage OWNER TO supabase_admin;

--
-- Name: VIEW model_proxy_hourly_usage; Type: COMMENT; Schema: public; Owner: supabase_admin
--

COMMENT ON VIEW public.model_proxy_hourly_usage IS 'Hourly usage and cost tracking';


--
-- Name: model_proxy_performance; Type: VIEW; Schema: public; Owner: supabase_admin
--

CREATE VIEW public.model_proxy_performance AS
 SELECT model,
    count(*) AS total_requests,
    count(
        CASE
            WHEN (status_code = 200) THEN 1
            ELSE NULL::integer
        END) AS successful_requests,
    count(
        CASE
            WHEN (status_code <> 200) THEN 1
            ELSE NULL::integer
        END) AS failed_requests,
    round(((100.0 * (count(
        CASE
            WHEN (status_code = 200) THEN 1
            ELSE NULL::integer
        END))::numeric) / (count(*))::numeric), 2) AS success_rate,
    avg(duration_ms) AS avg_duration_ms,
    percentile_cont((0.5)::double precision) WITHIN GROUP (ORDER BY ((duration_ms)::double precision)) AS median_duration_ms,
    percentile_cont((0.95)::double precision) WITHIN GROUP (ORDER BY ((duration_ms)::double precision)) AS p95_duration_ms,
    avg(total_tokens) AS avg_tokens,
    sum(total_cost_usd) AS total_cost_usd,
    avg(total_cost_usd) AS avg_cost_usd
   FROM public.model_proxy_api_requests
  GROUP BY model;


ALTER VIEW public.model_proxy_performance OWNER TO supabase_admin;

--
-- Name: VIEW model_proxy_performance; Type: COMMENT; Schema: public; Owner: supabase_admin
--

COMMENT ON VIEW public.model_proxy_performance IS 'Model performance metrics and statistics';


--
-- Name: model_proxy_pricing; Type: TABLE; Schema: public; Owner: supabase_admin
--

CREATE TABLE public.model_proxy_pricing (
    id integer NOT NULL,
    model_name character varying(100),
    prompt_price_per_1k numeric(10,6),
    completion_price_per_1k numeric(10,6),
    effective_date timestamp with time zone DEFAULT now(),
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.model_proxy_pricing OWNER TO supabase_admin;

--
-- Name: TABLE model_proxy_pricing; Type: COMMENT; Schema: public; Owner: supabase_admin
--

COMMENT ON TABLE public.model_proxy_pricing IS 'Stores pricing information for different models';


--
-- Name: model_proxy_pricing_id_seq; Type: SEQUENCE; Schema: public; Owner: supabase_admin
--

CREATE SEQUENCE public.model_proxy_pricing_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.model_proxy_pricing_id_seq OWNER TO supabase_admin;

--
-- Name: model_proxy_pricing_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: supabase_admin
--

ALTER SEQUENCE public.model_proxy_pricing_id_seq OWNED BY public.model_proxy_pricing.id;


--
-- Name: model_proxy_tool_executions; Type: TABLE; Schema: public; Owner: supabase_admin
--

CREATE TABLE public.model_proxy_tool_executions (
    id bigint NOT NULL,
    request_id uuid,
    tool_call_id character varying(255),
    function_name character varying(255),
    arguments jsonb,
    result text,
    execution_time_ms integer,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.model_proxy_tool_executions OWNER TO supabase_admin;

--
-- Name: TABLE model_proxy_tool_executions; Type: COMMENT; Schema: public; Owner: supabase_admin
--

COMMENT ON TABLE public.model_proxy_tool_executions IS 'Logs tool execution results';


--
-- Name: model_proxy_tool_executions_id_seq; Type: SEQUENCE; Schema: public; Owner: supabase_admin
--

CREATE SEQUENCE public.model_proxy_tool_executions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.model_proxy_tool_executions_id_seq OWNER TO supabase_admin;

--
-- Name: model_proxy_tool_executions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: supabase_admin
--

ALTER SEQUENCE public.model_proxy_tool_executions_id_seq OWNED BY public.model_proxy_tool_executions.id;


--
-- Name: model_proxy_api_messages id; Type: DEFAULT; Schema: public; Owner: supabase_admin
--

ALTER TABLE ONLY public.model_proxy_api_messages ALTER COLUMN id SET DEFAULT nextval('public.model_proxy_api_messages_id_seq'::regclass);


--
-- Name: model_proxy_api_requests id; Type: DEFAULT; Schema: public; Owner: supabase_admin
--

ALTER TABLE ONLY public.model_proxy_api_requests ALTER COLUMN id SET DEFAULT nextval('public.model_proxy_api_requests_id_seq'::regclass);


--
-- Name: model_proxy_api_tools id; Type: DEFAULT; Schema: public; Owner: supabase_admin
--

ALTER TABLE ONLY public.model_proxy_api_tools ALTER COLUMN id SET DEFAULT nextval('public.model_proxy_api_tools_id_seq'::regclass);


--
-- Name: model_proxy_pricing id; Type: DEFAULT; Schema: public; Owner: supabase_admin
--

ALTER TABLE ONLY public.model_proxy_pricing ALTER COLUMN id SET DEFAULT nextval('public.model_proxy_pricing_id_seq'::regclass);


--
-- Name: model_proxy_tool_executions id; Type: DEFAULT; Schema: public; Owner: supabase_admin
--

ALTER TABLE ONLY public.model_proxy_tool_executions ALTER COLUMN id SET DEFAULT nextval('public.model_proxy_tool_executions_id_seq'::regclass);


--
-- Name: model_proxy_api_messages model_proxy_api_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: supabase_admin
--

ALTER TABLE ONLY public.model_proxy_api_messages
    ADD CONSTRAINT model_proxy_api_messages_pkey PRIMARY KEY (id);


--
-- Name: model_proxy_api_requests model_proxy_api_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: supabase_admin
--

ALTER TABLE ONLY public.model_proxy_api_requests
    ADD CONSTRAINT model_proxy_api_requests_pkey PRIMARY KEY (id);


--
-- Name: model_proxy_api_requests model_proxy_api_requests_request_id_key; Type: CONSTRAINT; Schema: public; Owner: supabase_admin
--

ALTER TABLE ONLY public.model_proxy_api_requests
    ADD CONSTRAINT model_proxy_api_requests_request_id_key UNIQUE (request_id);


--
-- Name: model_proxy_api_tools model_proxy_api_tools_pkey; Type: CONSTRAINT; Schema: public; Owner: supabase_admin
--

ALTER TABLE ONLY public.model_proxy_api_tools
    ADD CONSTRAINT model_proxy_api_tools_pkey PRIMARY KEY (id);


--
-- Name: model_proxy_pricing model_proxy_pricing_model_name_key; Type: CONSTRAINT; Schema: public; Owner: supabase_admin
--

ALTER TABLE ONLY public.model_proxy_pricing
    ADD CONSTRAINT model_proxy_pricing_model_name_key UNIQUE (model_name);


--
-- Name: model_proxy_pricing model_proxy_pricing_pkey; Type: CONSTRAINT; Schema: public; Owner: supabase_admin
--

ALTER TABLE ONLY public.model_proxy_pricing
    ADD CONSTRAINT model_proxy_pricing_pkey PRIMARY KEY (id);


--
-- Name: model_proxy_tool_executions model_proxy_tool_executions_pkey; Type: CONSTRAINT; Schema: public; Owner: supabase_admin
--

ALTER TABLE ONLY public.model_proxy_tool_executions
    ADD CONSTRAINT model_proxy_tool_executions_pkey PRIMARY KEY (id);


--
-- Name: idx_api_requests_app_project_time; Type: INDEX; Schema: public; Owner: supabase_admin
--

CREATE INDEX idx_api_requests_app_project_time ON public.model_proxy_api_requests USING btree (app_id, project_id, "timestamp" DESC);


--
-- Name: idx_api_requests_project_id; Type: INDEX; Schema: public; Owner: supabase_admin
--

CREATE INDEX idx_api_requests_project_id ON public.model_proxy_api_requests USING btree (project_id);


--
-- Name: idx_api_requests_provider; Type: INDEX; Schema: public; Owner: supabase_admin
--

CREATE INDEX idx_api_requests_provider ON public.model_proxy_api_requests USING btree (provider_name);


--
-- Name: idx_api_requests_route; Type: INDEX; Schema: public; Owner: supabase_admin
--

CREATE INDEX idx_api_requests_route ON public.model_proxy_api_requests USING btree (route);


--
-- Name: idx_api_requests_user_id; Type: INDEX; Schema: public; Owner: supabase_admin
--

CREATE INDEX idx_api_requests_user_id ON public.model_proxy_api_requests USING btree (user_id);


--
-- Name: idx_model_proxy_messages_request_id; Type: INDEX; Schema: public; Owner: supabase_admin
--

CREATE INDEX idx_model_proxy_messages_request_id ON public.model_proxy_api_messages USING btree (request_id);


--
-- Name: idx_model_proxy_messages_role; Type: INDEX; Schema: public; Owner: supabase_admin
--

CREATE INDEX idx_model_proxy_messages_role ON public.model_proxy_api_messages USING btree (role);


--
-- Name: idx_model_proxy_pricing_active; Type: INDEX; Schema: public; Owner: supabase_admin
--

CREATE INDEX idx_model_proxy_pricing_active ON public.model_proxy_pricing USING btree (model_name, is_active);


--
-- Name: idx_model_proxy_requests_app_id; Type: INDEX; Schema: public; Owner: supabase_admin
--

CREATE INDEX idx_model_proxy_requests_app_id ON public.model_proxy_api_requests USING btree (app_id);


--
-- Name: idx_model_proxy_requests_cost; Type: INDEX; Schema: public; Owner: supabase_admin
--

CREATE INDEX idx_model_proxy_requests_cost ON public.model_proxy_api_requests USING btree (total_cost_usd);


--
-- Name: idx_model_proxy_requests_created_at; Type: INDEX; Schema: public; Owner: supabase_admin
--

CREATE INDEX idx_model_proxy_requests_created_at ON public.model_proxy_api_requests USING btree (created_at);


--
-- Name: idx_model_proxy_requests_model; Type: INDEX; Schema: public; Owner: supabase_admin
--

CREATE INDEX idx_model_proxy_requests_model ON public.model_proxy_api_requests USING btree (model);


--
-- Name: idx_model_proxy_requests_progress_id; Type: INDEX; Schema: public; Owner: supabase_admin
--

CREATE INDEX idx_model_proxy_requests_progress_id ON public.model_proxy_api_requests USING btree (progress_id);


--
-- Name: idx_model_proxy_requests_request_id; Type: INDEX; Schema: public; Owner: supabase_admin
--

CREATE INDEX idx_model_proxy_requests_request_id ON public.model_proxy_api_requests USING btree (request_id);


--
-- Name: idx_model_proxy_requests_timestamp; Type: INDEX; Schema: public; Owner: supabase_admin
--

CREATE INDEX idx_model_proxy_requests_timestamp ON public.model_proxy_api_requests USING btree ("timestamp");


--
-- Name: idx_model_proxy_tool_executions_request_id; Type: INDEX; Schema: public; Owner: supabase_admin
--

CREATE INDEX idx_model_proxy_tool_executions_request_id ON public.model_proxy_tool_executions USING btree (request_id);


--
-- Name: idx_model_proxy_tools_request_id; Type: INDEX; Schema: public; Owner: supabase_admin
--

CREATE INDEX idx_model_proxy_tools_request_id ON public.model_proxy_api_tools USING btree (request_id);


--
-- Name: model_proxy_api_requests model_proxy_update_api_requests_updated_at; Type: TRIGGER; Schema: public; Owner: supabase_admin
--

CREATE TRIGGER model_proxy_update_api_requests_updated_at BEFORE UPDATE ON public.model_proxy_api_requests FOR EACH ROW EXECUTE FUNCTION public.model_proxy_update_updated_at_column();


--
-- Name: model_proxy_pricing model_proxy_update_pricing_updated_at; Type: TRIGGER; Schema: public; Owner: supabase_admin
--

CREATE TRIGGER model_proxy_update_pricing_updated_at BEFORE UPDATE ON public.model_proxy_pricing FOR EACH ROW EXECUTE FUNCTION public.model_proxy_update_updated_at_column();


--
-- Name: model_proxy_api_messages model_proxy_api_messages_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: supabase_admin
--

ALTER TABLE ONLY public.model_proxy_api_messages
    ADD CONSTRAINT model_proxy_api_messages_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.model_proxy_api_requests(request_id) ON DELETE CASCADE;


--
-- Name: model_proxy_api_tools model_proxy_api_tools_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: supabase_admin
--

ALTER TABLE ONLY public.model_proxy_api_tools
    ADD CONSTRAINT model_proxy_api_tools_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.model_proxy_api_requests(request_id) ON DELETE CASCADE;


--
-- Name: model_proxy_tool_executions model_proxy_tool_executions_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: supabase_admin
--

ALTER TABLE ONLY public.model_proxy_tool_executions
    ADD CONSTRAINT model_proxy_tool_executions_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.model_proxy_api_requests(request_id) ON DELETE CASCADE;


--
-- Name: model_proxy_api_messages Allow authenticated read access; Type: POLICY; Schema: public; Owner: supabase_admin
--

CREATE POLICY "Allow authenticated read access" ON public.model_proxy_api_messages FOR SELECT TO authenticated USING (true);


--
-- Name: model_proxy_api_requests Allow authenticated read access; Type: POLICY; Schema: public; Owner: supabase_admin
--

CREATE POLICY "Allow authenticated read access" ON public.model_proxy_api_requests FOR SELECT TO authenticated USING (true);


--
-- Name: model_proxy_api_tools Allow authenticated read access; Type: POLICY; Schema: public; Owner: supabase_admin
--

CREATE POLICY "Allow authenticated read access" ON public.model_proxy_api_tools FOR SELECT TO authenticated USING (true);


--
-- Name: model_proxy_pricing Allow authenticated read access; Type: POLICY; Schema: public; Owner: supabase_admin
--

CREATE POLICY "Allow authenticated read access" ON public.model_proxy_pricing FOR SELECT TO authenticated USING (true);


--
-- Name: model_proxy_tool_executions Allow authenticated read access; Type: POLICY; Schema: public; Owner: supabase_admin
--

CREATE POLICY "Allow authenticated read access" ON public.model_proxy_tool_executions FOR SELECT TO authenticated USING (true);


--
-- Name: model_proxy_api_messages Allow service role full access; Type: POLICY; Schema: public; Owner: supabase_admin
--

CREATE POLICY "Allow service role full access" ON public.model_proxy_api_messages TO service_role USING (true);


--
-- Name: model_proxy_api_requests Allow service role full access; Type: POLICY; Schema: public; Owner: supabase_admin
--

CREATE POLICY "Allow service role full access" ON public.model_proxy_api_requests TO service_role USING (true);


--
-- Name: model_proxy_api_tools Allow service role full access; Type: POLICY; Schema: public; Owner: supabase_admin
--

CREATE POLICY "Allow service role full access" ON public.model_proxy_api_tools TO service_role USING (true);


--
-- Name: model_proxy_pricing Allow service role full access; Type: POLICY; Schema: public; Owner: supabase_admin
--

CREATE POLICY "Allow service role full access" ON public.model_proxy_pricing TO service_role USING (true);


--
-- Name: model_proxy_tool_executions Allow service role full access; Type: POLICY; Schema: public; Owner: supabase_admin
--

CREATE POLICY "Allow service role full access" ON public.model_proxy_tool_executions TO service_role USING (true);


--
-- Name: model_proxy_api_messages; Type: ROW SECURITY; Schema: public; Owner: supabase_admin
--

ALTER TABLE public.model_proxy_api_messages ENABLE ROW LEVEL SECURITY;

--
-- Name: model_proxy_api_requests; Type: ROW SECURITY; Schema: public; Owner: supabase_admin
--

ALTER TABLE public.model_proxy_api_requests ENABLE ROW LEVEL SECURITY;

--
-- Name: model_proxy_api_tools; Type: ROW SECURITY; Schema: public; Owner: supabase_admin
--

ALTER TABLE public.model_proxy_api_tools ENABLE ROW LEVEL SECURITY;

--
-- Name: model_proxy_pricing; Type: ROW SECURITY; Schema: public; Owner: supabase_admin
--

ALTER TABLE public.model_proxy_pricing ENABLE ROW LEVEL SECURITY;

--
-- Name: model_proxy_tool_executions; Type: ROW SECURITY; Schema: public; Owner: supabase_admin
--

ALTER TABLE public.model_proxy_tool_executions ENABLE ROW LEVEL SECURITY;

--
-- Name: TABLE model_proxy_api_messages; Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON TABLE public.model_proxy_api_messages TO postgres;
GRANT ALL ON TABLE public.model_proxy_api_messages TO anon;
GRANT ALL ON TABLE public.model_proxy_api_messages TO authenticated;
GRANT ALL ON TABLE public.model_proxy_api_messages TO service_role;


--
-- Name: SEQUENCE model_proxy_api_messages_id_seq; Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON SEQUENCE public.model_proxy_api_messages_id_seq TO postgres;
GRANT ALL ON SEQUENCE public.model_proxy_api_messages_id_seq TO anon;
GRANT ALL ON SEQUENCE public.model_proxy_api_messages_id_seq TO authenticated;
GRANT ALL ON SEQUENCE public.model_proxy_api_messages_id_seq TO service_role;


--
-- Name: TABLE model_proxy_api_requests; Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON TABLE public.model_proxy_api_requests TO postgres;
GRANT ALL ON TABLE public.model_proxy_api_requests TO anon;
GRANT ALL ON TABLE public.model_proxy_api_requests TO authenticated;
GRANT ALL ON TABLE public.model_proxy_api_requests TO service_role;


--
-- Name: SEQUENCE model_proxy_api_requests_id_seq; Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON SEQUENCE public.model_proxy_api_requests_id_seq TO postgres;
GRANT ALL ON SEQUENCE public.model_proxy_api_requests_id_seq TO anon;
GRANT ALL ON SEQUENCE public.model_proxy_api_requests_id_seq TO authenticated;
GRANT ALL ON SEQUENCE public.model_proxy_api_requests_id_seq TO service_role;


--
-- Name: TABLE model_proxy_api_tools; Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON TABLE public.model_proxy_api_tools TO postgres;
GRANT ALL ON TABLE public.model_proxy_api_tools TO anon;
GRANT ALL ON TABLE public.model_proxy_api_tools TO authenticated;
GRANT ALL ON TABLE public.model_proxy_api_tools TO service_role;


--
-- Name: SEQUENCE model_proxy_api_tools_id_seq; Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON SEQUENCE public.model_proxy_api_tools_id_seq TO postgres;
GRANT ALL ON SEQUENCE public.model_proxy_api_tools_id_seq TO anon;
GRANT ALL ON SEQUENCE public.model_proxy_api_tools_id_seq TO authenticated;
GRANT ALL ON SEQUENCE public.model_proxy_api_tools_id_seq TO service_role;


--
-- Name: TABLE model_proxy_cost_summary; Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON TABLE public.model_proxy_cost_summary TO postgres;
GRANT ALL ON TABLE public.model_proxy_cost_summary TO anon;
GRANT ALL ON TABLE public.model_proxy_cost_summary TO authenticated;
GRANT ALL ON TABLE public.model_proxy_cost_summary TO service_role;


--
-- Name: TABLE model_proxy_hourly_usage; Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON TABLE public.model_proxy_hourly_usage TO postgres;
GRANT ALL ON TABLE public.model_proxy_hourly_usage TO anon;
GRANT ALL ON TABLE public.model_proxy_hourly_usage TO authenticated;
GRANT ALL ON TABLE public.model_proxy_hourly_usage TO service_role;


--
-- Name: TABLE model_proxy_performance; Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON TABLE public.model_proxy_performance TO postgres;
GRANT ALL ON TABLE public.model_proxy_performance TO anon;
GRANT ALL ON TABLE public.model_proxy_performance TO authenticated;
GRANT ALL ON TABLE public.model_proxy_performance TO service_role;


--
-- Name: TABLE model_proxy_pricing; Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON TABLE public.model_proxy_pricing TO postgres;
GRANT ALL ON TABLE public.model_proxy_pricing TO anon;
GRANT ALL ON TABLE public.model_proxy_pricing TO authenticated;
GRANT ALL ON TABLE public.model_proxy_pricing TO service_role;


--
-- Name: SEQUENCE model_proxy_pricing_id_seq; Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON SEQUENCE public.model_proxy_pricing_id_seq TO postgres;
GRANT ALL ON SEQUENCE public.model_proxy_pricing_id_seq TO anon;
GRANT ALL ON SEQUENCE public.model_proxy_pricing_id_seq TO authenticated;
GRANT ALL ON SEQUENCE public.model_proxy_pricing_id_seq TO service_role;


--
-- Name: TABLE model_proxy_tool_executions; Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON TABLE public.model_proxy_tool_executions TO postgres;
GRANT ALL ON TABLE public.model_proxy_tool_executions TO anon;
GRANT ALL ON TABLE public.model_proxy_tool_executions TO authenticated;
GRANT ALL ON TABLE public.model_proxy_tool_executions TO service_role;


--
-- Name: SEQUENCE model_proxy_tool_executions_id_seq; Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON SEQUENCE public.model_proxy_tool_executions_id_seq TO postgres;
GRANT ALL ON SEQUENCE public.model_proxy_tool_executions_id_seq TO anon;
GRANT ALL ON SEQUENCE public.model_proxy_tool_executions_id_seq TO authenticated;
GRANT ALL ON SEQUENCE public.model_proxy_tool_executions_id_seq TO service_role;


--
-- PostgreSQL database dump complete
--

\unrestrict evSFOjdrIB0qsizkOCt4aQuabCDXssCubADIohlohiRmGPedGUcw7cc65e4cxJQ

