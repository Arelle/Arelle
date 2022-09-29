-- This DDL (SQL) script initializes a database for the XBRL Open Model using Postgres
-- See COPYRIGHT.md for copyright information.

SET statement_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = off;
SET check_function_bodies = false;
SET client_min_messages = warning;
SET escape_string_warning = off;

SET search_path = public, pg_catalog;

-- drop tables and sequences
DROP TABLE IF EXISTS submission CASCADE;
DROP TABLE IF EXISTS filing CASCADE;
DROP TABLE IF EXISTS report CASCADE;
DROP TABLE IF EXISTS document CASCADE;
DROP TABLE IF EXISTS referenced_documents CASCADE;
DROP TABLE IF EXISTS element CASCADE;
DROP TABLE IF EXISTS data_type CASCADE;
DROP TABLE IF EXISTS enumeration CASCADE;
DROP TABLE IF EXISTS role_type CASCADE;
DROP TABLE IF EXISTS arcrole_type CASCADE;
DROP TABLE IF EXISTS used_on CASCADE;
DROP TABLE IF EXISTS resource CASCADE;
DROP TABLE IF EXISTS reference_part CASCADE;
DROP TABLE IF EXISTS relationship_set CASCADE;
DROP TABLE IF EXISTS relationship CASCADE;
DROP TABLE IF EXISTS root CASCADE;
DROP TABLE IF EXISTS fact CASCADE;
DROP TABLE IF EXISTS footnote CASCADE;
DROP TABLE IF EXISTS entity_identifier CASCADE;
DROP TABLE IF EXISTS period CASCADE;
DROP TABLE IF EXISTS unit CASCADE;
DROP TABLE IF EXISTS unit_measure CASCADE;
DROP TABLE IF EXISTS aspect_value_report_set CASCADE;
DROP TABLE IF EXISTS aspect_value_set CASCADE;
DROP TABLE IF EXISTS table_facts CASCADE;
DROP TABLE IF EXISTS message CASCADE;
DROP TABLE IF EXISTS message_reference CASCADE;

DROP SEQUENCE IF EXISTS seq_submission;
DROP SEQUENCE IF EXISTS seq_object;
DROP SEQUENCE IF EXISTS seq_relationship_set;
DROP SEQUENCE IF EXISTS seq_message;

--
-- note that dropping table also drops the indexes and triggers
--
CREATE SEQUENCE seq_submission;
ALTER TABLE public.seq_submission OWNER TO postgres;

CREATE TABLE submission (
    submission_pk bigint DEFAULT nextval('seq_submission'::regclass) NOT NULL,
    accepted_timestamp timestamp without time zone DEFAULT now() NOT NULL,
    loaded_timestamp timestamp without time zone DEFAULT now() NOT NULL,
    PRIMARY KEY (submission_pk)
);

ALTER TABLE public.submission OWNER TO postgres;


-- object sequence can be any element that can terminate a relationship (element, type, resource, data point, document, role type, ...)
-- or be a reference of a message (report or any of above)
CREATE SEQUENCE seq_object;
ALTER TABLE public.seq_object OWNER TO postgres;

CREATE TABLE filing (
    filing_pk bigint DEFAULT nextval('seq_object'::regclass) NOT NULL,
    filer_id character varying(64), -- could be LEI or authority specific
    PRIMARY KEY (filing_pk)
);

ALTER TABLE public.filing OWNER TO postgres;

CREATE TABLE report (
    report_pk bigint DEFAULT nextval('seq_object'::regclass) NOT NULL,
    submission_fk bigint NOT NULL,
    filing_fk bigint NOT NULL,
    report_id character varying(128), -- uniquely identifies report, authority specific
    is_most_current boolean DEFAULT false NOT NULL,
    creation_software text,
    report_data_doc_fk bigint,  -- instance or primary inline document
    report_schema_doc_fk bigint,  -- extension schema of the report (primary)
    PRIMARY KEY (report_pk)
);
CREATE INDEX report_index02 ON report USING btree (submission_fk);
CREATE INDEX report_index03 ON report USING btree (filing_fk);


ALTER TABLE public.report OWNER TO postgres;

CREATE TABLE document (
    document_pk bigint DEFAULT nextval('seq_object'::regclass) NOT NULL,
    url character varying(2048) NOT NULL,
    type character varying(32),  -- ModelDocument.Type string value
    namespace character varying(1024),  -- targetNamespace if schema else NULL
    PRIMARY KEY (document_pk)
);
CREATE INDEX document_index02 ON document USING hash (url);

ALTER TABLE public.document OWNER TO postgres;
-- documents referenced by report or document

CREATE TABLE referenced_documents (
    object_fk bigint NOT NULL,
    document_fk bigint NOT NULL
);
CREATE INDEX referenced_documents_index01 ON referenced_documents USING btree (object_fk);
CREATE UNIQUE INDEX referenced_documents_index02 ON referenced_documents USING btree (object_fk, document_fk);

ALTER TABLE public.referenced_documents OWNER TO postgres;

CREATE TABLE element (
    element_pk bigint DEFAULT nextval('seq_object'::regclass) NOT NULL,
    document_fk bigint NOT NULL,
    xml_id text,
    xml_child_seq character varying(1024),
    qname character varying(1024) NOT NULL,  -- clark notation qname (do we need this?)
    name character varying(1024) NOT NULL,  -- local qname
    datatype_fk bigint,
    base_type character varying(128), -- xml base type if any
    substitution_group_element_fk bigint,
    parent_element_fk bigint, -- tuple parent
    balance character varying(16),
    period_type character varying(16),
    abstract boolean NOT NULL,
    nillable boolean NOT NULL,
    is_numeric boolean NOT NULL,
    is_monetary boolean NOT NULL,
    is_text_block boolean NOT NULL,
    PRIMARY KEY (element_pk)
);
CREATE INDEX element_index02 ON element USING btree (document_fk);
CREATE INDEX element_index03 ON element USING hash (qname);

ALTER TABLE public.element OWNER TO postgres;

CREATE TABLE data_type (
    data_type_pk bigint DEFAULT nextval('seq_object'::regclass) NOT NULL,
    document_fk bigint NOT NULL,
    xml_id text,
    xml_child_seq character varying(1024),
    qname character varying(1024) NOT NULL,  -- clark notation qname (do we need this?)
    name character varying(1024) NOT NULL,  -- local qname
    base_type character varying(128), -- xml base type if any
    derived_from_type_fk bigint,
    length int, -- facets
    max_length int,
    min_length int,
    pattern character varying,
    PRIMARY KEY (data_type_pk)
);
CREATE INDEX data_type_index02 ON data_type USING btree (document_fk);
CREATE INDEX data_type_index03 ON data_type USING hash (qname);

ALTER TABLE public.data_type OWNER TO postgres;

CREATE TABLE enumeration (
    data_type_fk bigint NOT NULL,
    document_fk bigint NOT NULL,
    value text
);
CREATE INDEX enumeration_index01 ON enumeration USING btree (data_type_fk);
CREATE INDEX enumeration_index02 ON enumeration USING btree (document_fk);

ALTER TABLE public.enumeration OWNER TO postgres;

CREATE TABLE role_type (
    role_type_pk bigint DEFAULT nextval('seq_object'::regclass) NOT NULL,
    document_fk bigint NOT NULL,
    xml_id text,
    xml_child_seq character varying(1024),
    role_uri character varying(1024) NOT NULL,
    definition text,
    PRIMARY KEY (role_type_pk)
);
CREATE INDEX role_type_index02 ON role_type USING btree (document_fk);
CREATE INDEX role_type_index03 ON role_type USING hash (role_uri);

ALTER TABLE public.role_type OWNER TO postgres;

CREATE TABLE arcrole_type (
    arcrole_type_pk bigint DEFAULT nextval('seq_object'::regclass) NOT NULL,
    document_fk bigint NOT NULL,
    xml_id text,
    xml_child_seq character varying(1024),
    arcrole_uri character varying(1024) NOT NULL,
    cycles_allowed character varying(10) NOT NULL,
    definition text,
    PRIMARY KEY (arcrole_type_pk)
);
CREATE INDEX arcrole_type_index02 ON arcrole_type USING btree (document_fk);
CREATE INDEX arcrole_type_index03 ON arcrole_type USING hash (arcrole_uri);

ALTER TABLE public.arcrole_type OWNER TO postgres;

CREATE TABLE used_on (
    object_fk bigint NOT NULL,
    element_fk bigint NOT NULL
);
CREATE INDEX used_on_index01 ON used_on USING btree (object_fk);
CREATE UNIQUE INDEX used_on_index02 ON used_on USING btree (object_fk, element_fk);

ALTER TABLE public.used_on OWNER TO postgres;

CREATE TABLE resource (
    resource_pk bigint DEFAULT nextval('seq_object'::regclass) NOT NULL,
    document_fk bigint NOT NULL,
    xml_id text,
    xml_child_seq character varying(1024),
    qname character varying(1024) NOT NULL,  -- clark notation qname (do we need this?)
    role character varying(1024),
    value text,
    xml_lang character varying(16),
    PRIMARY KEY (resource_pk)
);
CREATE INDEX resource_index02 ON resource USING btree (document_fk, xml_child_seq);

ALTER TABLE public.resource OWNER TO postgres;

CREATE TABLE reference_part (
    resource_pk bigint NOT NULL,
    document_fk bigint NOT NULL,
    xml_child_seq character varying(1024),
    element_fk bigint, -- declaration of part
    value text
);
CREATE INDEX reference_part_index01 ON reference_part USING btree (resource_pk);
CREATE INDEX reference_part_index02 ON reference_part USING btree (document_fk);

ALTER TABLE public.reference_part OWNER TO postgres;

CREATE SEQUENCE seq_relationship_set;
ALTER TABLE public.seq_relationship_set OWNER TO postgres;

CREATE TABLE relationship_set (
    relationship_set_pk bigint DEFAULT nextval('seq_relationship_set'::regclass) NOT NULL,
    document_fk bigint NOT NULL,
    arc_qname character varying(1024) NOT NULL,  -- clark notation qname (do we need this?)
    link_qname character varying(1024) NOT NULL,  -- clark notation qname (do we need this?)
    arc_role character varying(1024) NOT NULL,
    link_role character varying(1024) NOT NULL,
    PRIMARY KEY (relationship_set_pk)
);
CREATE INDEX relationship_set_index02 ON relationship_set USING btree (document_fk); 
CREATE INDEX relationship_set_index03 ON relationship_set USING hash (arc_role); 
CREATE INDEX relationship_set_index04 ON relationship_set USING hash (link_role); 

ALTER TABLE public.relationship_set OWNER TO postgres;

CREATE TABLE root (
    relationship_set_fk bigint NOT NULL,
    relationship_fk bigint NOT NULL
);
CREATE INDEX root_index01 ON root USING btree (relationship_set_fk); 

ALTER TABLE public.root OWNER TO postgres;


CREATE TABLE relationship (
    relationship_pk bigint DEFAULT nextval('seq_object'::regclass) NOT NULL,
    document_fk bigint NOT NULL,
    xml_id text,
    xml_child_seq character varying(1024),
    relationship_set_fk bigint NOT NULL,
    reln_order double precision,
    from_fk bigint,
    to_fk bigint,
    calculation_weight double precision,
    tree_sequence integer NOT NULL,
    tree_depth integer NOT NULL,
    preferred_label_role character varying(1024),
    PRIMARY KEY (relationship_pk)
);
CREATE INDEX relationship_index02 ON relationship USING btree (relationship_set_fk); 
CREATE INDEX relationship_index03 ON relationship USING btree (relationship_set_fk, tree_depth); 
CREATE INDEX relationship_index04 ON relationship USING btree (relationship_set_fk, document_fk, xml_child_seq);
CREATE INDEX relationship_index05 ON relationship USING btree (from_fk);

ALTER TABLE public.relationship OWNER TO postgres;

CREATE TABLE fact (
    fact_pk bigint DEFAULT nextval('seq_object'::regclass) NOT NULL,
    report_fk bigint,
    document_fk bigint NOT NULL,  -- multiple inline documents are sources of data points
    xml_id text,
    xml_child_seq character varying(1024),
    source_line integer,
    tuple_fact_fk bigint, -- id of tuple parent
    element_fk bigint NOT NULL,
    context_xml_id character varying(1024), -- (do we need this?)
    entity_identifier_fk bigint,
    period_fk bigint,
    aspect_value_set_fk bigint,
    unit_fk bigint,
    is_nil boolean DEFAULT FALSE,
    precision_value character varying(16),
    decimals_value character varying(16),
    effective_value double precision,
    language character varying(16), -- for string-valued facts else NULL
    normalized_string_value character varying,
    value text,
    PRIMARY KEY (fact_pk)
);
CREATE INDEX fact_index02 ON fact USING btree (document_fk, xml_child_seq);
CREATE INDEX fact_index03 ON fact USING btree (report_fk);
CREATE INDEX fact_index04 ON fact USING btree (element_fk);

ALTER TABLE public.fact OWNER TO postgres;

CREATE TABLE footnote (
    fact_fk bigint NOT NULL,
    footnote_group character varying(1024),
    type character varying(1024),
    footnote_value_fk character varying(1024),
    language character varying(30),
    normalized_string_value text,
    value text
);
CREATE INDEX footnote_index01 ON footnote USING btree (fact_fk);


ALTER TABLE public.footnote OWNER TO postgres;

CREATE TABLE entity_identifier (
    entity_identifier_pk bigint DEFAULT nextval('seq_object'::regclass) NOT NULL,
    report_fk bigint,
    scheme character varying NOT NULL,
    identifier character varying NOT NULL,
    PRIMARY KEY (entity_identifier_pk)
);
CREATE INDEX entity_identifier_index02 ON entity_identifier USING btree (report_fk, identifier);

ALTER TABLE public.entity_identifier OWNER TO postgres;

CREATE TABLE period (
    period_pk bigint DEFAULT nextval('seq_object'::regclass) NOT NULL,
    report_fk bigint,
    start_date date,
    end_date date,
    is_instant boolean NOT NULL,
    is_forever boolean NOT NULL,
    PRIMARY KEY (period_pk)
);
CREATE INDEX period_index02 ON period USING btree (report_fk, start_date, end_date, is_instant, is_forever);

ALTER TABLE public.period OWNER TO postgres;

CREATE TABLE unit (
    unit_pk bigint DEFAULT nextval('seq_object'::regclass) NOT NULL,
    report_fk bigint,
    xml_id text,
    xml_child_seq character varying(1024),
    measures_hash char(32),
    PRIMARY KEY (unit_pk)
);
CREATE INDEX unit_index02 ON unit USING btree (report_fk, measures_hash);

ALTER TABLE public.unit OWNER TO postgres;


CREATE TABLE unit_measure (
    unit_pk bigint NOT NULL,
    qname character varying(1024) NOT NULL,  -- clark notation qname (do we need this?)
    is_multiplicand boolean NOT NULL
);
CREATE INDEX unit_measure_index01 ON unit_measure USING btree (unit_pk);
CREATE INDEX unit_measure_index02 ON unit_measure USING btree (unit_pk, (right(qname,16)), is_multiplicand);

ALTER TABLE public.unit_measure OWNER TO postgres;

-- table to create aspect_value_set_pk's for a report's aspect_value_sets
CREATE TABLE aspect_value_report_set (
    aspect_value_set_pk bigint DEFAULT nextval('seq_object'::regclass) NOT NULL,
    report_fk bigint
);
CREATE INDEX aspect_value_report_set_index01 ON aspect_value_report_set (report_fk);

ALTER TABLE public.aspect_value_report_set OWNER TO postgres;


CREATE TABLE aspect_value_set (
    aspect_value_set_fk bigint NOT NULL, -- index assigned by aspect_value_report_set
    aspect_element_fk bigint NOT NULL,
    aspect_value_fk bigint,
    is_typed_value boolean,
    typed_value text
);
CREATE INDEX aspect_value_setindex01 ON aspect_value_set USING btree (aspect_value_set_fk);
CREATE INDEX aspect_value_setindex02 ON aspect_value_set USING btree (aspect_element_fk);

ALTER TABLE public.aspect_value_set OWNER TO postgres;

CREATE TABLE table_facts(
    report_fk bigint,
    object_fk bigint NOT NULL, -- may be any role_type or element defining a table table with 'seq_object' id
    table_code character varying(16),  -- short code of table, like BS, PL, or 4.15.221
    fact_fk bigint -- id of fact in this table (according to its elements)
);
CREATE INDEX table_facts_index01 ON table_facts USING btree (report_fk);
CREATE INDEX table_facts_index02 ON table_facts USING btree (table_code);
CREATE INDEX table_facts_index03 ON table_facts USING btree (fact_fk);

CREATE SEQUENCE seq_message;
ALTER TABLE public.seq_message OWNER TO postgres;

CREATE TABLE message (
    message_pk bigint DEFAULT nextval('seq_message'::regclass) NOT NULL,
    report_fk bigint,
    sequence_in_report int,
    message_code character varying(256),
    message_level character varying(256),
    value text,
    PRIMARY KEY (message_pk)
);
CREATE INDEX message_index02 ON message USING btree (report_fk, sequence_in_report);

ALTER TABLE public.message OWNER TO postgres;

CREATE TABLE message_reference (
    message_fk bigint NOT NULL,
    object_fk bigint NOT NULL -- may be any table with 'seq_object' id
);
CREATE INDEX message_reference_index01 ON message_reference USING btree (message_fk);
CREATE UNIQUE INDEX message_reference_index02 ON message_reference USING btree (message_fk, object_fk);

ALTER TABLE public.message_reference OWNER TO postgres;


