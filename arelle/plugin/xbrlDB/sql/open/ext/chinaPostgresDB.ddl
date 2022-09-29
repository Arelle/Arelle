-- This DDL (SQL) script initializes China CAS/SASAC extension tables for the XBRL Open Model using Postgres
-- See COPYRIGHT.md for copyright information.

SET statement_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = off;
SET check_function_bodies = false;
SET client_min_messages = warning;
SET escape_string_warning = off;

SET search_path = public, pg_catalog;

-- drop tables and sequences
DROP TABLE IF EXISTS filing_china CASCADE;

CREATE TABLE filing_china (
    filing_pk bigint NOT NULL,
    entity_name character varying,
    entity_province character varying,
    entity_approval_date character varying,
    entity_approval_number character varying,
    entity_sponsor character varying,
    entity_license_number character varying,
    entity_industries character varying,
    entity_ticker_symbol character varying,
    PRIMARY KEY (filing_pk)
);

ALTER TABLE public.filing_china OWNER TO postgres;
