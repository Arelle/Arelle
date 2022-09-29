-- This DDL (SQL) script initializes XDC extension tables for the XBRL Open Model using Postgres
-- See COPYRIGHT.md for copyright information.

SET statement_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = off;
SET check_function_bodies = false;
SET client_min_messages = warning;
SET escape_string_warning = off;

SET search_path = public, pg_catalog;

-- drop tables, sequences and views
DROP TABLE IF EXISTS xdc_user CASCADE;
DROP TABLE IF EXISTS submission_xdc CASCADE;
DROP TABLE IF EXISTS filing_xdc CASCADE;

DROP SEQUENCE IF EXISTS seq_xdc_user;

CREATE SEQUENCE seq_xdc_user;
ALTER TABLE public.seq_xdc_user OWNER TO postgres;

CREATE TABLE xdc_user (
    user_pk bigint DEFAULT nextval('seq_xdc_user'::regclass) NOT NULL,
    user_id character varying(64),
    name character varying,
    details character varying,
    PRIMARY KEY (user_id)
);
CREATE INDEX xdc_user_index02 ON xdc_user USING btree (user_id);

ALTER TABLE public.xdc_user OWNER TO postgres;


CREATE TABLE submission_xdc (
    submission_pk bigint NOT NULL,
    submitter_fk bigint NOT NULL,
    source_portal character varying(64),
    PRIMARY KEY (submission_pk)
);
CREATE INDEX submission_xdc_index02 ON submission_xdc USING btree (submission_pk);

ALTER TABLE public.submission_xdc OWNER TO postgres;

CREATE TABLE filing_xdc (
    filing_pk bigint NOT NULL,
    filing_id character varying(64),
    details character varying,
    PRIMARY KEY (filing_pk)
);

ALTER TABLE public.filing_xdc OWNER TO postgres;

CREATE OR REPLACE VIEW xdc_filing_attached_documents (
    filing_fk, filing_number, document_fk, document_url, document_type) AS
    SELECT filing_pk, filing_id, d.document_pk, d.url, d.type
    FROM filing_xdc as f, referenced_documents rd, document d 
    WHERE rd.object_fk = f.filing_pk and d.document_pk = rd.document_fk;

ALTER VIEW public.xdc_filing_attached_documents OWNER TO postgres;
    
CREATE MATERIALIZED VIEW xdc_element_labels (
    element_fk, element_semantic_label, common_label_cn, common_label_en, doc_label_cn, doc_label_en) AS
    SELECT e.element_pk, lse.value, lcc.value, lce.value, ldc.value, lde.value 
    FROM element e
    JOIN relationship rse ON e.element_pk = rse.from_fk
    JOIN relationship_set rs ON rse.relationship_set_fk = rs.relationship_set_pk
    JOIN resource lse ON rse.to_fk = lse.resource_pk AND lse.role = 'http://www.xbrl.org/2003/role/label' AND lse.xml_lang = 'en'
    LEFT JOIN relationship rcc ON e.element_pk = rcc.from_fk AND rcc.relationship_set_fk = rs.relationship_set_pk
         JOIN resource lcc ON rcc.to_fk = lcc.resource_pk AND lcc.role = 'http://www.changhong.com/XDC/role/commonLabel' AND lcc.xml_lang = 'cn'
    LEFT JOIN relationship rce ON e.element_pk = rce.from_fk AND rce.relationship_set_fk = rs.relationship_set_pk
         JOIN resource lce ON rce.to_fk = lce.resource_pk AND lce.role = 'http://www.changhong.com/XDC/role/commonLabel' AND lce.xml_lang = 'en'
    LEFT JOIN relationship rdc ON e.element_pk = rdc.from_fk AND rdc.relationship_set_fk = rs.relationship_set_pk
         JOIN resource ldc ON rdc.to_fk = ldc.resource_pk AND ldc.role = 'http://www.xbrl.org/2003/role/documentation' AND ldc.xml_lang = 'cn'
    LEFT JOIN relationship rde ON e.element_pk = rde.from_fk AND rde.relationship_set_fk = rs.relationship_set_pk
         JOIN resource lde ON rde.to_fk = lde.resource_pk AND lde.role = 'http://www.xbrl.org/2003/role/documentation' AND lde.xml_lang = 'en'
    WITH NO DATA;

ALTER VIEW public.xdc_element_labels OWNER TO postgres;
    
CREATE MATERIALIZED VIEW xdc_element_reference_parts (
    element_fk, element_semantic_label, reference_fk, reference_qname, part_qname, part_value) AS
    SELECT e.element_pk, l.value, p.resource_pk, r.qname, ep.qname, p.value
    FROM element e, relationship rp, resource r, reference_part p, 
         relationship_set rsp, element ep, resource l, relationship rl, relationship_set rsl 
    WHERE e.element_pk = rp.from_fk AND rp.to_fk = p.resource_pk AND 
          ep.element_pk = p.element_fk AND
          rp.relationship_set_fk = rsp.relationship_set_pk AND
          rsp.arc_role = 'http://www.xbrl.org/2003/arcrole/concept-reference' AND
          r.resource_pk = p.resource_pk AND
          e.element_pk = rl.from_fk AND rl.to_fk = l.resource_pk AND 
          l.role = 'http://www.xbrl.org/2003/role/label' AND l.xml_lang = 'en' AND
          rl.relationship_set_fk = rsl.relationship_set_pk AND
          rsl.arc_role = 'http://www.xbrl.org/2003/arcrole/concept-label'
    WITH NO DATA;
          
ALTER VIEW public.xdc_element_reference_parts OWNER TO postgres;

CREATE MATERIALIZED VIEW xdc_document_model (
    arc_set_fk, root_element_fk, root_element_name, type_element_fk, type_element_name,
    pre_source_fk, pre_source_url, schema_source_fk, schema_source_url) AS
    SELECT rs.relationship_set_pk, rel.from_fk, er.name, rel.to_fk, et.name, pre.document_pk, pre.url, sch.document_pk, sch.url
    FROM relationship_set rs, root rt, relationship rel, document sch, referenced_documents rd, document pre, element er, element et
    WHERE rs.document_fk = sch.document_pk AND rs.arc_role = 'http://www.xbrl.org/2003/arcrole/parent-child' AND
          rd.object_fk = sch.document_pk AND pre.document_pk = rd.document_fk AND pre.url like '%_pre.xml' AND
          rt.relationship_set_fk = rs.relationship_set_pk AND rel.relationship_pk = rt.relationship_fk AND
          er.element_pk = rel.from_fk AND et.element_pk = rel.to_fk
    WITH NO DATA;

ALTER VIEW public.xdc_document_model OWNER TO postgres;

CREATE OR REPLACE VIEW xdc_orders (
	report_fk, root_element_name, accounting_service_order_number) AS 
	SELECT DISTINCT report.report_pk, dm.root_element_name,
		fact.value
	FROM report
		JOIN document ifile ON report.report_data_doc_fk = ifile.document_pk
		JOIN xdc_document_model dm ON dm.schema_source_fk = report.report_schema_doc_fk
		JOIN fact ON fact.report_fk = report.report_pk
		JOIN element elm ON fact.element_fk = elm.element_pk
	WHERE 
		(dm.root_element_name='order_model_root')
		AND elm.name='accounting_service_order_number';

ALTER VIEW public.xdc_orders OWNER TO postgres;

CREATE OR REPLACE VIEW xdc_evidence (
	report_fk, root_element_name, accounting_service_order_number) AS 
	SELECT DISTINCT report.report_pk, dm.root_element_name,
		fact.value
	FROM report
		JOIN document ifile ON report.report_data_doc_fk = ifile.document_pk
		JOIN xdc_document_model dm ON dm.schema_source_fk = report.report_schema_doc_fk
		JOIN fact ON fact.report_fk = report.report_pk
		JOIN element elm ON fact.element_fk = elm.element_pk
	WHERE 
		(dm.root_element_name = 'ledger_model_template_root' 
		OR dm.root_element_name LIKE 'evidence_document_%' )
		AND elm.name = 'accounting_service_order_number';

ALTER VIEW public.xdc_evidence OWNER TO postgres;


CREATE OR REPLACE VIEW xdc_order_x_ledger_artifact (
		accounting_service_order_number, order_report_fk, child_report_fk, child_model_root) AS
	SELECT o.accounting_service_order_number, o.report_fk, 
		ev.report_fk, ev.root_element_name
	FROM xdc_evidence ev
		LEFT JOIN xdc_orders o ON ev.accounting_service_order_number = o.accounting_service_order_number
--	WHERE o.root_element_name = 'order_model_root'
;
	
ALTER VIEW public.xdc_order_x_ledger_artifact OWNER TO postgres;
    