--
-- PostgreSQL database dump
--

\restrict rcIpSzndGB6wlT0QtLx2jpxr5PS9efEpwBYnx3JN95gqrRayEeAg7iCXTX81nt9

-- Dumped from database version 17.6
-- Dumped by pg_dump version 17.6

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
-- Name: model_proxy_api_messages; Type: TABLE; Schema: public; Owner: -
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


--
-- Name: TABLE model_proxy_api_messages; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.model_proxy_api_messages IS 'Stores individual messages from API requests';


--
-- Name: model_proxy_api_messages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.model_proxy_api_messages_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: model_proxy_api_messages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.model_proxy_api_messages_id_seq OWNED BY public.model_proxy_api_messages.id;


--
-- Name: model_proxy_api_requests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.model_proxy_api_requests (
    id bigint NOT NULL,
    "timestamp" timestamp with time zone DEFAULT now(),
    request_id uuid DEFAULT extensions.uuid_generate_v4(),
    app_id integer,
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


--
-- Name: TABLE model_proxy_api_requests; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.model_proxy_api_requests IS 'Logs all API requests and responses to OpenAI models';


--
-- Name: COLUMN model_proxy_api_requests.provider_name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.model_proxy_api_requests.provider_name IS 'Provider name (openai, anthropic, local, etc.)';


--
-- Name: COLUMN model_proxy_api_requests.user_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.model_proxy_api_requests.user_id IS 'User identifier for user-level analytics';


--
-- Name: COLUMN model_proxy_api_requests.agent_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.model_proxy_api_requests.agent_id IS 'Agent identifier';


--
-- Name: COLUMN model_proxy_api_requests.project_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.model_proxy_api_requests.project_id IS 'Project identifier for multi-project tracking';


--
-- Name: COLUMN model_proxy_api_requests.cached_tokens; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.model_proxy_api_requests.cached_tokens IS 'Cached tokens (prompt caching) - reduces cost';


--
-- Name: COLUMN model_proxy_api_requests.metadata; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.model_proxy_api_requests.metadata IS 'Freeform JSON metadata (condensation stats, etc.)';


--
-- Name: model_proxy_api_requests_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.model_proxy_api_requests_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: model_proxy_api_requests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.model_proxy_api_requests_id_seq OWNED BY public.model_proxy_api_requests.id;


--
-- Name: model_proxy_api_tools; Type: TABLE; Schema: public; Owner: -
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


--
-- Name: TABLE model_proxy_api_tools; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.model_proxy_api_tools IS 'Stores tool/function definitions used in requests';


--
-- Name: model_proxy_api_tools_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.model_proxy_api_tools_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: model_proxy_api_tools_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.model_proxy_api_tools_id_seq OWNED BY public.model_proxy_api_tools.id;


--
-- Name: model_proxy_tool_executions; Type: TABLE; Schema: public; Owner: -
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


--
-- Name: TABLE model_proxy_tool_executions; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.model_proxy_tool_executions IS 'Logs tool execution results';


--
-- Name: model_proxy_tool_executions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.model_proxy_tool_executions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: model_proxy_tool_executions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.model_proxy_tool_executions_id_seq OWNED BY public.model_proxy_tool_executions.id;


--
-- Name: model_proxy_api_messages id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_proxy_api_messages ALTER COLUMN id SET DEFAULT nextval('public.model_proxy_api_messages_id_seq'::regclass);


--
-- Name: model_proxy_api_requests id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_proxy_api_requests ALTER COLUMN id SET DEFAULT nextval('public.model_proxy_api_requests_id_seq'::regclass);


--
-- Name: model_proxy_api_tools id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_proxy_api_tools ALTER COLUMN id SET DEFAULT nextval('public.model_proxy_api_tools_id_seq'::regclass);


--
-- Name: model_proxy_tool_executions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_proxy_tool_executions ALTER COLUMN id SET DEFAULT nextval('public.model_proxy_tool_executions_id_seq'::regclass);


--
-- Name: model_proxy_api_messages model_proxy_api_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_proxy_api_messages
    ADD CONSTRAINT model_proxy_api_messages_pkey PRIMARY KEY (id);


--
-- Name: model_proxy_api_requests model_proxy_api_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_proxy_api_requests
    ADD CONSTRAINT model_proxy_api_requests_pkey PRIMARY KEY (id);


--
-- Name: model_proxy_api_requests model_proxy_api_requests_request_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_proxy_api_requests
    ADD CONSTRAINT model_proxy_api_requests_request_id_key UNIQUE (request_id);


--
-- Name: model_proxy_api_tools model_proxy_api_tools_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_proxy_api_tools
    ADD CONSTRAINT model_proxy_api_tools_pkey PRIMARY KEY (id);


--
-- Name: model_proxy_tool_executions model_proxy_tool_executions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_proxy_tool_executions
    ADD CONSTRAINT model_proxy_tool_executions_pkey PRIMARY KEY (id);


--
-- Name: idx_api_requests_app_project_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_api_requests_app_project_time ON public.model_proxy_api_requests USING btree (app_id, project_id, "timestamp" DESC);


--
-- Name: idx_api_requests_project_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_api_requests_project_id ON public.model_proxy_api_requests USING btree (project_id);


--
-- Name: idx_api_requests_provider; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_api_requests_provider ON public.model_proxy_api_requests USING btree (provider_name);


--
-- Name: idx_api_requests_route; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_api_requests_route ON public.model_proxy_api_requests USING btree (route);


--
-- Name: idx_api_requests_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_api_requests_user_id ON public.model_proxy_api_requests USING btree (user_id);


--
-- Name: idx_model_proxy_messages_request_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_model_proxy_messages_request_id ON public.model_proxy_api_messages USING btree (request_id);


--
-- Name: idx_model_proxy_messages_role; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_model_proxy_messages_role ON public.model_proxy_api_messages USING btree (role);


--
-- Name: idx_model_proxy_requests_app_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_model_proxy_requests_app_id ON public.model_proxy_api_requests USING btree (app_id);


--
-- Name: idx_model_proxy_requests_cost; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_model_proxy_requests_cost ON public.model_proxy_api_requests USING btree (total_cost_usd);


--
-- Name: idx_model_proxy_requests_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_model_proxy_requests_created_at ON public.model_proxy_api_requests USING btree (created_at);


--
-- Name: idx_model_proxy_requests_model; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_model_proxy_requests_model ON public.model_proxy_api_requests USING btree (model);


--
-- Name: idx_model_proxy_requests_progress_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_model_proxy_requests_progress_id ON public.model_proxy_api_requests USING btree (progress_id);


--
-- Name: idx_model_proxy_requests_request_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_model_proxy_requests_request_id ON public.model_proxy_api_requests USING btree (request_id);


--
-- Name: idx_model_proxy_requests_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_model_proxy_requests_timestamp ON public.model_proxy_api_requests USING btree ("timestamp");


--
-- Name: idx_model_proxy_tool_executions_request_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_model_proxy_tool_executions_request_id ON public.model_proxy_tool_executions USING btree (request_id);


--
-- Name: idx_model_proxy_tools_request_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_model_proxy_tools_request_id ON public.model_proxy_api_tools USING btree (request_id);


--
-- Name: model_proxy_api_requests model_proxy_update_api_requests_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER model_proxy_update_api_requests_updated_at BEFORE UPDATE ON public.model_proxy_api_requests FOR EACH ROW EXECUTE FUNCTION public.model_proxy_update_updated_at_column();


--
-- Name: model_proxy_api_messages model_proxy_api_messages_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_proxy_api_messages
    ADD CONSTRAINT model_proxy_api_messages_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.model_proxy_api_requests(request_id) ON DELETE CASCADE;


--
-- Name: model_proxy_api_tools model_proxy_api_tools_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_proxy_api_tools
    ADD CONSTRAINT model_proxy_api_tools_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.model_proxy_api_requests(request_id) ON DELETE CASCADE;


--
-- Name: model_proxy_tool_executions model_proxy_tool_executions_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_proxy_tool_executions
    ADD CONSTRAINT model_proxy_tool_executions_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.model_proxy_api_requests(request_id) ON DELETE CASCADE;


--
-- Name: model_proxy_api_messages Allow authenticated read access; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "Allow authenticated read access" ON public.model_proxy_api_messages FOR SELECT TO authenticated USING (true);


--
-- Name: model_proxy_api_requests Allow authenticated read access; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "Allow authenticated read access" ON public.model_proxy_api_requests FOR SELECT TO authenticated USING (true);


--
-- Name: model_proxy_api_tools Allow authenticated read access; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "Allow authenticated read access" ON public.model_proxy_api_tools FOR SELECT TO authenticated USING (true);


--
-- Name: model_proxy_tool_executions Allow authenticated read access; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "Allow authenticated read access" ON public.model_proxy_tool_executions FOR SELECT TO authenticated USING (true);


--
-- Name: model_proxy_api_messages Allow service role full access; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "Allow service role full access" ON public.model_proxy_api_messages TO service_role USING (true);


--
-- Name: model_proxy_api_requests Allow service role full access; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "Allow service role full access" ON public.model_proxy_api_requests TO service_role USING (true);


--
-- Name: model_proxy_api_tools Allow service role full access; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "Allow service role full access" ON public.model_proxy_api_tools TO service_role USING (true);


--
-- Name: model_proxy_tool_executions Allow service role full access; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "Allow service role full access" ON public.model_proxy_tool_executions TO service_role USING (true);


--
-- Name: model_proxy_api_messages; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.model_proxy_api_messages ENABLE ROW LEVEL SECURITY;

--
-- Name: model_proxy_api_requests; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.model_proxy_api_requests ENABLE ROW LEVEL SECURITY;

--
-- Name: model_proxy_api_tools; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.model_proxy_api_tools ENABLE ROW LEVEL SECURITY;

--
-- Name: model_proxy_tool_executions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.model_proxy_tool_executions ENABLE ROW LEVEL SECURITY;

--
-- PostgreSQL database dump complete
--

\unrestrict rcIpSzndGB6wlT0QtLx2jpxr5PS9efEpwBYnx3JN95gqrRayEeAg7iCXTX81nt9

