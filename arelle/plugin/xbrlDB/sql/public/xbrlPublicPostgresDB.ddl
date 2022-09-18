﻿--
-- XBRL-US Public Postgres DB 
--
-- PostgreSQL database dump
--

-- changes for Arelle:
-- 
-- 2013-12-01: Clear everything prior (drop schema and recreate) before loading ddl
--
-- 2014-01-02: Comment out fk_accession_entity as entity is not set up for non-RSS 
--             accessions and not known until later in instance loading.
--
--             Comment out namespace_taxonomy_version_id_fkey, no version information known
--             to arelle.
--
--             Comment out constraints and triggers not used in arelle; also the constraints
--             appear to block bulk loading of taxonomy.
 

-- clear everything prior
DROP SCHEMA public CASCADE; create SCHEMA public;

SET statement_timeout = 0;
SET client_encoding = 'UTF8';
-- HF - must have conforming strings on for Postgres interface to work, as it will include Windows paths sometimes
SET standard_conforming_strings = on;
SET check_function_bodies = false;
SET client_min_messages = warning;
SET escape_string_warning = off;

SET search_path = public, pg_catalog;

--
-- Name: ancestry; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE ancestry AS (
	network_id integer,
	ancestry_path integer,
	depth integer,
	from_namesapce character varying,
	from_local_name character varying,
	from_element_id integer,
	to_namespace character varying,
	to_local_name character varying,
	to_element_id integer,
	reln_order double precision,
	calculation_weight double precision
);


ALTER TYPE public.ancestry OWNER TO postgres;

--
-- Name: industry_hierarchy; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE industry_hierarchy AS (
	industry_classification character varying,
	industry_id integer,
	depth integer,
	industry_code integer,
	industry_name character varying,
	industry_description character varying,
	parent_id integer
);


ALTER TYPE public.industry_hierarchy OWNER TO postgres;

--
-- Name: accession_complete(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION accession_complete() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
        run_update boolean;
BEGIN
        IF (TG_OP = 'DELETE') THEN
                --Delete entity name hsitory records that were created by the accession
                DELETE FROM entity_name_history
                WHERE accession_id = OLD.accession_id;

                RETURN OLD;
        ELSE
                run_update := false;
                IF (TG_OP = 'INSERT') THEN
                        IF (NEW.is_complete = true) THEN
                                run_update := true;
                        END IF;
                ELSIF (TG_OP = 'UPDATE') THEN
                        IF (coalesce(OLD.is_complete,false) = false AND NEW.is_complete = true) THEN
                                run_update := true;
                        END IF;
                END IF;

                IF (run_update) THEN
                        PERFORM update_specifies_dimensions_by_accession(NEW.accession_id);
                        PERFORM update_namespace_by_accession(NEW.accession_id);
                        PERFORM update_context_aug_by_accession(NEW.accession_id);
                        PERFORM update_fact_aug_by_accession(NEW.accession_id);
			PERFORM update_fact_by_accession(NEW.accession_id);
                        PERFORM update_accession_element_by_accession(NEW.accession_id);
                        PERFORM update_entity_name_history(NEW);
                        --PERFORM update_unique_label_by_accession(NEW.accession_id);
                END IF;
                RETURN NEW;
        END IF;
END;

$$;


ALTER FUNCTION public.accession_complete() OWNER TO postgres;

--
-- Name: accession_restatement_period_index(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION accession_restatement_period_index() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
	run_update boolean := false;
	acc_record RECORD;
BEGIN
	-- Check to see if the is_complete was changed to true. This is the condition when the
	-- restatement and period index should be recalculated.
	CASE
		WHEN (TG_OP = 'UPDATE') THEN
			IF (coalesce(OLD.is_complete,false) = false AND NEW.is_complete = true) THEN
				run_update := true;
				acc_record := NEW;
			END IF;
		WHEN (TG_OP = 'INSERT') THEN
			IF (NEW.is_complete = true) THEN
				run_update := true;
				acc_record := NEW;
			END IF;
		WHEN (TG_OP = 'DELETE') THEN
			run_update := true;
			acc_record := OLD;
	END CASE;

	IF (run_update) THEN
		-- Recalc the restatement_index and is_most_current for the entity of the accession
		UPDATE accession ua
		SET restatement_index = rn
		FROM (SELECT row_number() over(w) AS rn, entity_id, accepted_timestamp, period_end, accession_id
		      FROM (SELECT entity_id, accepted_timestamp, accession.accession_id, period_end
			    FROM accession
			    JOIN (SELECT f.accession_id, max(c.period_end) period_end
			          FROM fact f
			          JOIN element e
			            ON f.element_id = e.element_id
			          JOIN qname q
			            ON e.qname_id = q.qname_id
			          JOIN context c
			            ON f.context_id = c.context_id
			          JOIN accession a
			            ON f.accession_id = a.accession_id
			          WHERE q.namespace like '%/dei/%'
				    AND q.local_name = 'DocumentPeriodEndDate'
				    AND a.entity_id = acc_record.entity_id
				  GROUP BY f.accession_id) accession_period_end
			      ON accession.accession_id = accession_period_end.accession_id
			    WHERE accession.entity_id = acc_record.entity_id) accession_list

		WINDOW w AS (partition BY entity_id, period_end ORDER BY accepted_timestamp DESC)) AS x
		WHERE ua.accession_id = x.accession_id
		  AND coalesce(restatement_index,0) <> rn;

		-- Recalc the period index for the
		UPDATE accession ua
		SET period_index = rn
		   ,is_most_current = CASE WHEN rn = 1 THEN true ELSE false END
		FROM (SELECT row_number() over(w) AS rn, entity_id, accepted_timestamp, period_end, accession_id, restatement_index
		      FROM (SELECT entity_id, accepted_timestamp, accession.accession_id, period_end, restatement_index
			    FROM accession
			    JOIN (SELECT f.accession_id, max(c.period_end) period_end
			          FROM fact f
			          JOIN element e
			            ON f.element_id = e.element_id
			          JOIN qname q
			            ON e.qname_id = q.qname_id
			          JOIN context c
			            ON f.context_id = c.context_id
			          JOIN accession a
			            ON f.accession_id = a.accession_id
			          WHERE q.namespace like '%/dei/%'
				    AND q.local_name = 'DocumentPeriodEndDate'
				    AND a.entity_id = acc_record.entity_id
				  GROUP BY f.accession_id) accession_period_end
			      ON accession.accession_id = accession_period_end.accession_id
			    WHERE accession.entity_id = acc_record.entity_id) accession_list

		WINDOW w AS (partition BY entity_id ORDER BY period_end DESC, restatement_index ASC)) AS x
		WHERE ua.accession_id = x.accession_id;
		
		UPDATE entity e 
		SET entity_name = a.entity_name 
		FROM (SELECT entity_id, entity_name FROM accession WHERE entity_id = acc_record.entity_id AND period_index = 1) as a
		WHERE e.entity_id = a.entity_id;
		
	END IF;
		
	RETURN acc_record;

END
$$;


ALTER FUNCTION public.accession_restatement_period_index() OWNER TO postgres;

--
-- Name: accession_timestamp_add(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION accession_timestamp_add() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
begin

  insert into accession_timestamp (accession_id) values (NEW.accession_id);
  return NULL;

end;
$$;


ALTER FUNCTION public.accession_timestamp_add() OWNER TO postgres;

--
-- Name: ancestry_all(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION ancestry_all(child_id integer) RETURNS SETOF ancestry
    LANGUAGE plpgsql
    AS $$
DECLARE
               network_id_working       integer;
BEGIN

               FOR network_id_working IN SELECT DISTINCT n.network_id
                                             FROM  network n
                                             JOIN relationship rel
                                                ON n.network_id = rel.network_id
                                             WHERE rel.from_element_id = child_id
                                               OR  rel.to_element_id = child_id
               LOOP
                              RETURN QUERY SELECT * FROM ancestry_in_network(network_id_working, child_id);
               END LOOP;


               RETURN;
END
$$;


ALTER FUNCTION public.ancestry_all(child_id integer) OWNER TO postgres;

--
-- Name: ancestry_all(character varying); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION ancestry_all(child_name character varying) RETURNS SETOF ancestry
    LANGUAGE plpgsql
    AS $$
DECLARE
               child_element_id              integer;
BEGIN
               FOR child_element_id IN SELECT e.element_id
                                                            FROM   element e
                                                            JOIN qname qe
                                                              ON e.qname_id = qe.qname_id
                                                            WHERE qe.local_name = child_name
               LOOP
                              RETURN QUERY SELECT * FROM ancestry_all(child_element_id);

               END LOOP;
               RETURN;
END
$$;


ALTER FUNCTION public.ancestry_all(child_name character varying) OWNER TO postgres;

--
-- Name: ancestry_compose_paths(integer, integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION ancestry_compose_paths(relationship_id_arg integer, depth integer DEFAULT 0) RETURNS SETOF ancestry
    LANGUAGE plpgsql
    AS $$
DECLARE
               child_row                           relationship;
               i                                            integer;
               new_path_row                 ancestry;

BEGIN
               -- Get the current relationship
               SELECT ar.network_id
                     ,ap.path_num
                     ,depth
                     ,fqe.namespace
                     ,fqe.local_name
                     ,ar.from_element_id
                     ,tqe.namespace
                     ,tqe.local_name
                     ,ar.to_element_id
                     ,ar.reln_order
                     ,ar.calculation_weight
               INTO new_path_row
               FROM         ancestry_rels ar
                              JOIN element fe
                                ON ar.from_element_id = fe.element_id
                              JOIN qname fqe
                                ON fe.qname_id = fqe.qname_id
                              JOIN element te
                                ON ar.to_element_id = te.element_id
                              JOIN qname tqe
                                ON te.qname_id = tqe.qname_id
                              ,ancestry_path ap
               WHERE relationship_id = relationship_id_arg;

               RETURN NEXT new_path_row;

               i := 0;
               FOR child_row IN SELECT *
                                             FROM ancestry_rels
                                             WHERE from_element_id = new_path_row.to_element_id
               LOOP
                                             RETURN QUERY SELECT * FROM ancestry_compose_paths(child_row.relationship_id, depth + 1);
                                             i := i + 1;
               END LOOP;

               -- There are no children. -->
               IF i = 0 THEN
                              UPDATE ancestry_path SET path_num = path_num + 1;
               END IF;




END
$$;


ALTER FUNCTION public.ancestry_compose_paths(relationship_id_arg integer, depth integer) OWNER TO postgres;

--
-- Name: seq_relationship; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE seq_relationship
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.seq_relationship OWNER TO postgres;

SET default_tablespace = '';

SET default_with_oids = false;

--
-- Name: relationship; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE relationship (
    relationship_id integer DEFAULT nextval('seq_relationship'::regclass) NOT NULL,
    network_id integer NOT NULL,
    from_element_id integer,
    to_element_id integer,
    reln_order double precision,
    from_resource_id integer,
    to_resource_id integer,
    calculation_weight double precision,
    tree_sequence integer NOT NULL,
    tree_depth integer NOT NULL,
    preferred_label_role_uri_id integer
);


ALTER TABLE public.relationship OWNER TO postgres;

--
-- Name: COLUMN relationship.from_resource_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN relationship.from_resource_id IS 'Not used in base XBRL 2.1, but legal nonetheless';


--
-- Name: COLUMN relationship.calculation_weight; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN relationship.calculation_weight IS 'Obviously only for calculation relationships';


--
-- Name: ancestry_get_relationships(integer, integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION ancestry_get_relationships(network_id_arg integer, child_id integer) RETURNS SETOF relationship
    LANGUAGE plpgsql
    AS $$
DECLARE
               curRel relationship;
BEGIN

               FOR curRel IN
                              SELECT rel.*
                              FROM   network n
                                JOIN relationship rel
                                  ON n.network_id = rel.network_id
                                JOIN element from_e
                                  ON rel.from_element_id = from_e.element_id
                                JOIN element to_e
                                  ON rel.to_element_id = to_e.element_id
                                JOIN qname from_q
                                  ON from_e.qname_id = from_q.qname_id
                                JOIN qname to_q
                                  ON to_e.qname_id = to_q.qname_id
                              WHERE n.network_id = network_id_arg
                                AND to_e.element_id = child_id

               LOOP
                                  return next  curRel;
                                  return query SELECT * FROM ancestry_get_relationships(network_id_arg, curRel.from_element_id);
               END LOOP;
               return;
END
$$;


ALTER FUNCTION public.ancestry_get_relationships(network_id_arg integer, child_id integer) OWNER TO postgres;

--
-- Name: ancestry_in_accession(integer, character varying); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION ancestry_in_accession(accession_id_arg integer, child_name character varying) RETURNS SETOF ancestry
    LANGUAGE plpgsql
    AS $$
DECLARE
               network_id_working       integer;
               child_element_id              integer;
BEGIN
               FOR child_element_id IN SELECT e.element_id
                                                     FROM   element e
                                                     JOIN qname qe
                                                       ON e.qname_id = qe.qname_id
                                                     WHERE qe.local_name = child_name
               LOOP
                              RETURN QUERY SELECT * FROM ancestry_in_accession(accession_id_arg, child_element_id);

               END LOOP;
               RETURN;
END
$$;


ALTER FUNCTION public.ancestry_in_accession(accession_id_arg integer, child_name character varying) OWNER TO postgres;

--
-- Name: ancestry_in_accession(integer, integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION ancestry_in_accession(accession_id_arg integer, child_id integer) RETURNS SETOF ancestry
    LANGUAGE plpgsql
    AS $$
DECLARE
               network_id_working       integer;
BEGIN

               FOR network_id_working IN SELECT DISTINCT n.network_id
                                             FROM  network n
                                             JOIN relationship rel
                                                ON n.network_id = rel.network_id
                                             WHERE (rel.from_element_id = child_id
                                               OR  rel.to_element_id = child_id)
                                             AND  accession_id = accession_id_arg


               LOOP
                              RETURN QUERY SELECT * FROM ancestry_in_network(network_id_working, child_id);
               END LOOP;


               RETURN;
END
$$;


ALTER FUNCTION public.ancestry_in_accession(accession_id_arg integer, child_id integer) OWNER TO postgres;

--
-- Name: ancestry_in_network(integer, integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION ancestry_in_network(network_id_arg integer, child_id integer) RETURNS SETOF ancestry
    LANGUAGE plpgsql
    AS $$
DECLARE
               ancestry_relationship      ancestry;
               ancestry_relationships    ancestry[];
               out                                       ancestry;
               roots                                   relationship;
               path                                     ancestry[];
               i                                            integer;
BEGIN
               DROP TABLE IF EXISTS ancestry_rels;

               CREATE TEMP TABLE ancestry_rels AS
               SELECT DISTINCT *
               FROM ancestry_get_relationships (network_id_arg, child_id);

               DROP TABLE IF EXISTS ancestry_path;

               CREATE TEMP TABLE ancestry_path (path_num integer);
               INSERT INTO ancestry_path (path_num) VALUES (0);

               i := 0;


               -- find the roots to start processing
               FOR roots IN SELECT *
                              FROM ancestry_rels ar1
                              WHERE NOT EXISTS (
                                             SELECT *
                                             FROM ancestry_rels ar2
                                             WHERE ar1.from_element_id = ar2.to_element_id)
               LOOP
                              RETURN QUERY SELECT * FROM ancestry_compose_paths(roots.relationship_id, 0);
               END LOOP;
               RETURN;

END
$$;


ALTER FUNCTION public.ancestry_in_network(network_id_arg integer, child_id integer) OWNER TO postgres;

--
-- Name: ancestry_in_network(integer, character varying); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION ancestry_in_network(network_id_arg integer, child_name character varying) RETURNS SETOF ancestry
    LANGUAGE plpgsql
    AS $$
DECLARE
               child_element_id              integer;
BEGIN
               FOR child_element_id IN SELECT e.element_id
                                                            FROM   element e
                                                            JOIN qname qe
                                                              ON e.qname_id = qe.qname_id
                                                            WHERE qe.local_name = child_name
               LOOP
                              RETURN QUERY SELECT * FROM ancestry_in_network(network_id_arg, child_element_id);

               END LOOP;
               RETURN;
END
$$;


ALTER FUNCTION public.ancestry_in_network(network_id_arg integer, child_name character varying) OWNER TO postgres;

--
-- Name: armor(bytea); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION armor(bytea) RETURNS text
    LANGUAGE c IMMUTABLE STRICT
    AS '$libdir/pgcrypto', 'pg_armor';


ALTER FUNCTION public.armor(bytea) OWNER TO postgres;

--
-- Name: array_remove_value(anyarray, anyarray); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION array_remove_value(orig_array_arg anyarray, item anyarray) RETURNS anyarray
    LANGUAGE plpgsql
    AS $$
DECLARE
             result    orig_array_arg%TYPE;
             i            int;
             x            varchar;
BEGIN
             FOR i IN array_lower(orig_array_arg,1)..array_upper(orig_array_arg,1) LOOP
                           IF orig_array_arg[i:i] <> array[item] THEN
                                        SELECT result || orig_array_arg[i:i] INTO result;
                           END IF;
             END LOOP;
 
             RETURN result;
END 
$$;


ALTER FUNCTION public.array_remove_value(orig_array_arg anyarray, item anyarray) OWNER TO postgres;

--
-- Name: base_element_hash_string(character varying, character varying); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION base_element_hash_string(element_namespace character varying, element_local_name character varying) RETURNS character varying
    LANGUAGE plpgsql
    AS $$             
DECLARE
	ns_prefix character varying;
BEGIN
	SELECT 'b' || t.taxonomy_id || ':' || n.prefix
	INTO ns_prefix
	FROM taxonomy t
	JOIN taxonomy_version tv
	  ON t.taxonomy_id = tv.taxonomy_id
	JOIN namespace n
	  ON tv.taxonomy_version_id = n.taxonomy_version_id
	WHERE n.uri = element_namespace
	  AND n.is_base;

	RETURN ns_prefix || ':' || element_local_name;

END

$$;


ALTER FUNCTION public.base_element_hash_string(element_namespace character varying, element_local_name character varying) OWNER TO postgres;

--
-- Name: base_element_id(character varying, character varying); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION base_element_id(element_namespace character varying, element_local_name character varying) RETURNS integer
    LANGUAGE plpgsql
    AS $$
DECLARE
	taxonomy_id_var integer;
	element_id_ret integer;
BEGIN

	SELECT tv.taxonomy_id
	INTO taxonomy_id_var
	FROM taxonomy_version tv
	JOIN namespace n
	  ON tv.taxonomy_version_id = n.taxonomy_version_id
	WHERE n.uri = element_namespace
	  AND n.is_base = true;

	SELECT min(e.element_id)
	INTO element_id_ret
	FROM element e
	JOIN qname q
	  ON e.qname_id = q.qname_id
	JOIN namespace n
	  ON q.namespace = n.uri
	JOIN taxonomy_version tv
	  ON n.taxonomy_version_id = tv.taxonomy_version_id
	WHERE tv.taxonomy_id = taxonomy_id_var
	  AND q.local_name = element_local_name;

	RETURN element_id_ret;

END
$$;


ALTER FUNCTION public.base_element_id(element_namespace character varying, element_local_name character varying) OWNER TO postgres;

--
-- Name: base_taxonomy_name(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION base_taxonomy_name(accession_id_arg integer) RETURNS character varying
    LANGUAGE plpgsql
    AS $$
DECLARE
             result    character varying;
BEGIN
 
             SELECT t.name || ' ' || tv.version
             INTO result
             FROM taxonomy t
             JOIN taxonomy_version tv
               ON t.taxonomy_id = tv.taxonomy_id
             WHERE tv.taxonomy_version_id = base_taxonomy_version(accession_id_arg);
 
             RETURN result;
END
$$;


ALTER FUNCTION public.base_taxonomy_name(accession_id_arg integer) OWNER TO postgres;

--
-- Name: base_taxonomy_version(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION base_taxonomy_version(accession_id_arg integer) RETURNS integer
    LANGUAGE plpgsql
    AS $$
DECLARE
               return_taxonomy_version integer;
BEGIN
               SELECT n.taxonomy_version_id
               INTO return_taxonomy_version
               FROM   fact f
                 JOIN accession a
                   ON f.accession_id = a.accession_id
                 JOIN element e
                   ON f.element_id = e.element_id
                 JOIN qname qe
                   ON e.qname_id = qe.qname_id
                 JOIN namespace n
                   on qe.namespace = n.uri
               WHERE qe.local_name = 'DocumentType'
               AND   n.prefix = 'dei'
               AND   a.accession_id = accession_id_arg;

               RETURN return_taxonomy_version;
END
$$;


ALTER FUNCTION public.base_taxonomy_version(accession_id_arg integer) OWNER TO postgres;

--
-- Name: calc_calendar_ultimus(bytea); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION calc_calendar_ultimus(hash_string bytea) RETURNS integer
    LANGUAGE plpgsql
    AS $$
DECLARE
               index_count integer;
               fact_aug_cursor CURSOR FOR SELECT fa.calendar_hash
                                                                           , fa.fact_id, a.accepted_timestamp
                                                                           , ca.calendar_period_size_diff_percentage
                                                                           , ca.calendar_end_offset
                                                                           , f.calendar_ultimus_index
                                                            FROM fact_aug fa
                                                            JOIN fact f
                                                              ON fa.fact_id = f.fact_id
                                                            JOIN accession a
                                                              ON f.accession_id = a.accession_id
                                                            JOIN context_aug ca
                                                              ON f.context_id = ca.context_id
                                                            WHERE fa.calendar_hash = hash_string
                                                              AND ca.calendar_end_offset is not null
                                                            ORDER BY fa.calendar_hash
                                                                           , a.accepted_timestamp desc
                                                                           , f.accession_id desc
                                                                           , abs(ca.calendar_period_size_diff_percentage)
                                                                           , abs(ca.calendar_end_offset)
                                                                           , fa.fact_id desc
                                                            FOR UPDATE;
BEGIN
               index_count := 0;

               FOR fact_aug_row IN fact_aug_cursor LOOP
                              index_count := index_count + 1;
                                             
                              UPDATE fact_aug
                              SET calendar_ultimus_index = index_count
                              WHERE CURRENT OF fact_aug_cursor;

                              UPDATE fact
                              SET calendar_ultimus_index = index_count
                              WHERE CURRENT OF fact_aug_cursor;
               END LOOP;
               
	       RETURN index_count;
END

$$;


ALTER FUNCTION public.calc_calendar_ultimus(hash_string bytea) OWNER TO postgres;

--
-- Name: calc_fact_aug(bytea); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION calc_fact_aug(hash_string bytea) RETURNS integer
    LANGUAGE plpgsql
    AS $$
DECLARE
               index_count integer;
               fact_aug_cursor CURSOR FOR SELECT fa.fact_hash, fa.fact_id, f.ultimus_index, a.accepted_timestamp
                                                            FROM fact_aug fa
                                                            JOIN fact f
                                                              ON fa.fact_id = f.fact_id
                                                            JOIN accession a
                                                              ON f.accession_id = a.accession_id
                                                            WHERE fa.fact_hash = hash_string
                                                            ORDER BY fa.fact_hash, a.accepted_timestamp desc, f.accession_id desc, fa.fact_id desc
                                                            FOR UPDATE;
BEGIN
               index_count := 0;

               FOR fact_aug_row IN fact_aug_cursor LOOP
                              index_count := index_count + 1;
                                             
                              UPDATE fact_aug
                              SET ultimus_index = index_count
                              WHERE CURRENT OF fact_aug_cursor;

                              UPDATE fact
                              SET ultimus_index = index_count
                              WHERE CURRENT OF fact_aug_cursor;
               END LOOP;

	       RETURN index_count;

END
$$;


ALTER FUNCTION public.calc_fact_aug(hash_string bytea) OWNER TO postgres;

--
-- Name: calendar_end_offset(date); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION calendar_end_offset(instant_arg date) RETURNS numeric
    LANGUAGE plpgsql
    AS $$
BEGIN
               RETURN (calendar_period_full(instant_arg)).calendar_end_offset;
END
$$;


ALTER FUNCTION public.calendar_end_offset(instant_arg date) OWNER TO postgres;

--
-- Name: calendar_end_offset(date, date); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION calendar_end_offset(start_arg date, end_arg date) RETURNS numeric
    LANGUAGE plpgsql
    AS $$
BEGIN
               RETURN (calendar_period_full(start_arg, end_arg)).calendar_end_offset;
END
$$;


ALTER FUNCTION public.calendar_end_offset(start_arg date, end_arg date) OWNER TO postgres;

--
-- Name: calendar_period(date); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION calendar_period(instant_arg date) RETURNS character varying
    LANGUAGE plpgsql
    AS $$
BEGIN
               RETURN (calendar_period_full(instant_arg)).calendar_period;
END
$$;


ALTER FUNCTION public.calendar_period(instant_arg date) OWNER TO postgres;

--
-- Name: calendar_period(date, date); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION calendar_period(start_arg date, end_arg date) RETURNS character varying
    LANGUAGE plpgsql
    AS $$
BEGIN
               RETURN (calendar_period_full(start_arg, end_arg)).calendar_period;
END
$$;


ALTER FUNCTION public.calendar_period(start_arg date, end_arg date) OWNER TO postgres;

--
-- Name: calendar_period_full(date); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION calendar_period_full(instant_arg date, OUT calendar_period character varying, OUT calendar_year integer, OUT calendar_start_offset numeric, OUT calendar_end_offset numeric, OUT calendar_period_size_diff_percentage double precision) RETURNS record
    LANGUAGE plpgsql
    AS $$
DECLARE
               year_part integer;
               period character varying;

BEGIN

               calendar_year := extract(YEAR FROM instant_arg);

               SELECT INTO year_part extract(YEAR FROM  instant_arg);

               -- Start with the first quarter
               calendar_end_offset := DATE (year_to_char(year_part) || '-04-01') - instant_arg;
               calendar_period := '1Q';

               -- Check if the June 30th is closer (q2)
               IF abs(calendar_end_offset) > abs(DATE (year_to_char(year_part) || '-07-01') - instant_arg) THEN
                              calendar_end_offset := DATE (year_to_char(year_part) || '-07-01') - instant_arg;
                              calendar_period := '2Q';
               END IF;

               -- Check if the September 30th is closer (q3)
               IF abs(calendar_end_offset) > abs(DATE (year_to_char(year_part) || '-10-01') - instant_arg) THEN
                              calendar_end_offset := DATE (year_to_char(year_part) || '-10-01') - instant_arg;
                              calendar_period := '3Q';
               END IF;

               -- Check if the December 31st is closer (y)
               IF abs(calendar_end_offset) > abs(DATE (year_to_char(year_part + 1) || '-01-01') - instant_arg) THEN
                              calendar_end_offset := DATE (year_to_char(year_part + 1) || '-01-01') - instant_arg;
                              calendar_period := 'Y';
               END IF;

               -- Check if the the previous year end is closer (y)
               IF abs(calendar_end_offset) > abs(DATE (year_to_char(year_part) || '-01-01') - instant_arg) THEN
                              calendar_end_offset := DATE (year_to_char(year_part) || '-01-01') - instant_arg;
                              calendar_period := 'Y';
                              calendar_year := calendar_year - 1;
               END IF;

               calendar_start_offset := null;
               calendar_period_size_diff_percentage := null;

               RETURN;


END
$$;


ALTER FUNCTION public.calendar_period_full(instant_arg date, OUT calendar_period character varying, OUT calendar_year integer, OUT calendar_start_offset numeric, OUT calendar_end_offset numeric, OUT calendar_period_size_diff_percentage double precision) OWNER TO postgres;

--
-- Name: seq_context; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE seq_context
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.seq_context OWNER TO postgres;

--
-- Name: context; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE context (
    context_id integer DEFAULT nextval('seq_context'::regclass) NOT NULL,
    accession_id integer NOT NULL,
    period_start date,
    period_end date,
    period_instant date,
    specifies_dimensions boolean NOT NULL,
    context_xml_id character varying(2048) NOT NULL,
    entity_scheme character varying(2048) NOT NULL,
    entity_identifier character varying(2048) NOT NULL
);


ALTER TABLE public.context OWNER TO postgres;

--
-- Name: calendar_period_full(context); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION calendar_period_full(context_arg context, OUT calendar_period character varying, OUT calendar_year integer, OUT calendar_start_offset numeric, OUT calendar_end_offset numeric, OUT calendar_period_size_diff_percentage double precision) RETURNS record
    LANGUAGE plpgsql
    AS $$
DECLARE
               calendar RECORD;
BEGIN
               IF context_arg.period_instant is not null THEN
                              calendar :=  calendar_period_full(context_arg.period_instant);
               ELSE
                              calendar :=  calendar_period_full(context_arg.period_start, context_arg.period_end);
               END IF;

               calendar_period := calendar.calendar_period;
               calendar_year := calendar.calendar_year;
               calendar_start_offset := calendar.calendar_start_offset;
               calendar_end_offset := calendar.calendar_end_offset;
               calendar_period_size_diff_percentage := calendar.calendar_period_size_diff_percentage;


               RETURN;
END
$$;


ALTER FUNCTION public.calendar_period_full(context_arg context, OUT calendar_period character varying, OUT calendar_year integer, OUT calendar_start_offset numeric, OUT calendar_end_offset numeric, OUT calendar_period_size_diff_percentage double precision) OWNER TO postgres;

--
-- Name: calendar_period_full(date, date); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION calendar_period_full(start_arg date, end_arg date, OUT calendar_period character varying, OUT calendar_year integer, OUT calendar_start_offset numeric, OUT calendar_end_offset numeric, OUT calendar_period_size_diff_percentage double precision) RETURNS record
    LANGUAGE plpgsql
    AS $$
DECLARE
               period_length     integer;
               o_interval            interval;
               o_intervals          interval[];
               year_offset         integer;
               calendar_start    date;
               calendar_end     date;
               calendar_length double precision;
               found_period     boolean;
               special_year       boolean;

BEGIN
               period_length := end_arg - start_arg;
               year_offset := 0;
               found_period := true;
               special_year := false;

               CASE
                              -- quarters
                              WHEN period_length >= 81 AND period_length <= 101 THEN
                                             -- This assignment calculates the overlap of the supplied period with each of the calendar quarters.
                                             o_intervals := array[overlap_interval(start_arg, end_arg, date (year_to_char(EXTRACT(YEAR FROM start_arg)) || '-01-01'), date (EXTRACT(YEAR FROM start_arg) || '-03-31')),
                                                            overlap_interval(start_arg, end_arg, date (year_to_char(EXTRACT(YEAR FROM end_arg)) || '-01-01'), date (EXTRACT(YEAR FROM end_arg) || '-03-31')),

                                                            overlap_interval(start_arg, end_arg, date (year_to_char(EXTRACT(YEAR FROM start_arg)) || '-04-01'), date (EXTRACT(YEAR FROM start_arg) || '-06-30')),
                                                            overlap_interval(start_arg, end_arg, date (year_to_char(EXTRACT(YEAR FROM end_arg)) || '-04-01'), date (EXTRACT(YEAR FROM end_arg) || '-06-30')),

                                                            overlap_interval(start_arg, end_arg, date (year_to_char(EXTRACT(YEAR FROM start_arg)) || '-07-01'), date (EXTRACT(YEAR FROM start_arg) || '-09-30')),
                                                            overlap_interval(start_arg, end_arg, date (year_to_char(EXTRACT(YEAR FROM end_arg)) || '-07-01'), date (EXTRACT(YEAR FROM end_arg) || '-09-30')),

                                                            overlap_interval(start_arg, end_arg, date (year_to_char(EXTRACT(YEAR FROM start_arg)) || '-10-01'), date (EXTRACT(YEAR FROM start_arg) || '-12-31')),
                                                            overlap_interval(start_arg, end_arg, date (year_to_char(EXTRACT(YEAR FROM end_arg)) || '-10-01'), date (EXTRACT(YEAR FROM end_arg) || '-12-31'))];

                                             o_interval := greatest(o_intervals[1],o_intervals[2],o_intervals[3],o_intervals[4],o_intervals[5],o_intervalS[6],o_intervals[7],o_intervals[8]);

                                             CASE o_interval
                                                            WHEN o_intervals[1] THEN
                                                                           year_offset := -1;
                                                                           calendar_period := '1Q';
                                                            WHEN o_intervals[2] THEN

                                                                           calendar_period := '1Q';
                                                            WHEN o_intervals[3] THEN
                                                                           year_offset := -1;
                                                                           calendar_period := '2Q';
                                                            WHEN o_intervals[4] THEN

                                                                           calendar_period := '2Q';
                                                            WHEN o_intervals[5] THEN
                                                                           year_offset := -1;
                                                                           calendar_period := '3Q';
                                                            WHEN o_intervals[6] THEN

                                                                           calendar_period := '3Q';
                                                            WHEN o_intervals[7] THEN
                                                                           year_offset := -1;
                                                                           calendar_period := '4Q';
                                                            WHEN o_intervals[8] THEN

                                                                           calendar_period := '4Q';
                                                            ELSE
                                                                           year_offset := 0;
                                                                           found_period := false;
                                                                           calendar_period := to_char(start_arg,'yyyy-mm-dd') || ' - ' || to_char(end_arg,'yyyy-mm-dd');
                                             END CASE;

                              -- halves
                              WHEN period_length >= 172 AND period_length <= 192 THEN
                                             --This assignment calculates the overlap of the supplied period with first half and second half of the calendar year.
                                             --The array is the list of overlaps for h1 start, h1 end, h2 start and h2 end.
                                             o_intervals := array[overlap_interval(start_arg, end_arg, date (year_to_char(EXTRACT(YEAR FROM start_arg)) || '-01-01'), date (EXTRACT(YEAR FROM start_arg) || '-06-30')),
                                             overlap_interval(start_arg, end_arg, date (year_to_char(EXTRACT(YEAR FROM end_arg)) || '-01-01'), date (EXTRACT(YEAR FROM end_arg) || '-06-30')),
                                             overlap_interval(start_arg, end_arg, date (year_to_char(EXTRACT(YEAR FROM start_arg)) || '-07-01'), date (EXTRACT(YEAR FROM start_arg) || '-12-31')),
                                             overlap_interval(start_arg, end_arg, date (year_to_char(EXTRACT(YEAR FROM end_arg)) || '-07-01'), date (EXTRACT(YEAR FROM end_arg) || '-12-31'))];

                                             o_interval := greatest(o_intervals[1],o_intervals[2],o_intervals[3],o_intervals[4]);


                                             CASE o_interval
                                                            WHEN o_intervals[1] THEN
                                                                           year_offset := -1;
                                                                           calendar_period := '1H';
                                                            WHEN o_intervals[2] THEN

                                                                           calendar_period := '1H';
                                                            WHEN o_intervals[3] THEN
                                                                           year_offset := -1;
                                                                           calendar_period := '2H';
                                                            WHEN o_intervals[4] THEN

                                                                           calendar_period := '2H';
                                                            ELSE
                                                                           year_offset := 0;
                                                                           found_period := false;
                                                                           calendar_period := to_char(start_arg,'yyyy-mm-dd') || ' - ' || to_char(end_arg,'yyyy-mm-dd');
                                             END CASE;


                              --3Q CUM
                              WHEN period_length >= 263 AND period_length <= 283  THEN
                                             o_intervals := array[overlap_interval(start_arg, end_arg, date (year_to_char(EXTRACT(YEAR FROM start_arg)) || '-01-01'), date (EXTRACT(YEAR FROM start_arg) || '-09-30')),
                                                            overlap_interval(start_arg, end_arg, date (year_to_char(EXTRACT(YEAR FROM end_arg)) || '-01-01'), date (year_to_char(EXTRACT(YEAR FROM end_arg)) || '-09-30'))];
                                             o_interval := greatest(o_intervals[1], o_intervals[2]);
                                             CASE o_interval
                                                            WHEN o_intervals[1] THEN
                                                                           year_offset := -1;
                                                                           calendar_period := '3QCUM';
                                                            WHEN o_intervals[2] THEN

                                                                           calendar_period := '3QCUM';
                                                            ELSE
                                                                           year_offset := 0;
                                                                           found_period := false;
                                                                           calendar_period := to_char(start_arg,'yyyy-mm-dd') || ' - ' || to_char(end_arg,'yyyy-mm-dd');
                                             END CASE;
                              -- year
                              WHEN period_length >= 355 AND period_length <= 375 THEN
                                             -- This is a special case when a year period overlaps 3 years. For example, 2008-12-28 to 2010-01-04. This will calendar align to the middle year (2009).
                                             IF (extract(YEAR FROM end_arg) - extract(YEAR FROM start_arg)) = 2 THEN
                                                            year_offset := -1;
                                                            calendar_period := 'Y';
                                                            special_year := true;
                                             ELSE
                                                            o_intervals := array[overlap_interval(start_arg, end_arg, date (year_to_char(EXTRACT(YEAR FROM start_arg)) || '-01-01'), date (year_to_char(EXTRACT(YEAR FROM start_arg)) || '-12-31')),
                                                                           overlap_interval(start_arg, end_arg, date (year_to_char(EXTRACT(YEAR FROM end_arg)) || '-01-01'), date (year_to_char(EXTRACT(YEAR FROM end_arg)) || '-12-31'))];
                                                            o_interval := greatest(o_intervals[1], o_intervals[2]);
                                                            CASE o_interval
                                                                           WHEN o_intervals[1] THEN
                                                                                          year_offset := -1;
                                                                                          calendar_period := 'Y';
                                                                           WHEN o_intervals[2] THEN

                                                                                          calendar_period := 'Y';
                                                                           ELSE
                                                                                          year_offset := 0;
                                                                                          found_period := false;
                                                                                          calendar_period := to_char(start_arg,'yyyy-mm-dd') || ' - ' || to_char(end_arg,'yyyy-mm-dd');
                                                            END CASE;

                                                            calendar_period := 'Y';
                                             END IF;
                              -- otherwise the period is unknown
                              ELSE
                                             o_interval := 0;
                                             year_offset := 0;
                                             found_period := false;
                                             calendar_period := to_char(start_arg,'yyyy-mm-dd') || ' - ' || to_char(end_arg,'yyyy-mm-dd');

               END CASE;

               -- Determine the calendar year.
               IF year_to_char(extract(YEAR FROM start_arg)) = year_to_char(extract(YEAR FROM end_arg)) THEN
                              calendar_year = extract(YEAR FROM start_arg);
               ELSE

                              IF found_period OR special_year THEN
                                             -- calculate the calendar year from the year offset.
                                             calendar_year := extract(YEAR FROM end_arg) + year_offset;
                              ELSE
                                             -- determine which year has the most overlap
                                             IF overlap_interval (start_arg, end_arg, (year_to_char(extract(YEAR FROM start_arg)) || '-01-01')::date, (year_to_char(extract(YEAR FROM start_arg)) || '-12-31')::date) >= overlap_interval (start_arg, end_arg, (year_to_char(extract(YEAR FROM end_arg)) || '-01-01')::date, (year_to_char(extract(YEAR FROM end_arg)) || '-12-31')::date) THEN
                                                            calendar_year = extract(YEAR FROM start_arg);
                                             ELSE
                                                            calendar_year = extract(YEAR FROM end_arg);
                                             END IF;
                              END IF;
               END IF;


               -- determine the slip.
               CASE calendar_period
                              WHEN '1Q' THEN
                                             calendar_start := (year_to_char(calendar_year) || '-01-01')::date;
                                             calendar_end := (year_to_char(calendar_year) || '-04-01')::date;
                              WHEN 'Y' THEN
                                             calendar_start := (year_to_char(calendar_year) || '-01-01')::date;
                                             calendar_end := (year_to_char(calendar_year+1) || '-01-01')::date;
                              WHEN '1H' THEN
                                             calendar_start := (year_to_char(calendar_year) || '-01-01')::date;
                                             calendar_end := (year_to_char(calendar_year) || '-07-01')::date;
                              WHEN '3QCUM' THEN
                                             calendar_start := (year_to_char(calendar_year) || '-01-01')::date;
                                             calendar_end := (year_to_char(calendar_year) || '-10-01')::date;
                              WHEN '2Q' THEN
                                             calendar_start := (year_to_char(calendar_year) || '-04-01')::date;
                                             calendar_end := (year_to_char(calendar_year) || '-07-01')::date;
                              WHEN '3Q' THEN
                                             calendar_start := (year_to_char(calendar_year) || '-07-01')::date;
                                             calendar_end := (year_to_char(calendar_year) || '-10-01')::date;
                              WHEN '2H' THEN
                                             calendar_start := (year_to_char(calendar_year) || '-07-01')::date;
                                             calendar_end := (year_to_char(calendar_year + 1) || '-01-01')::date;
                              WHEN '4Q' THEN
                                             calendar_start := (year_to_char(calendar_year) || '-10-01')::date;
                                             calendar_end := (year_to_char(calendar_year + 1) || '-01-01')::date;
                              ELSE
                                             calendar_start := null;
                                             calendar_end := null;
               END CASE;

               calendar_start_offset := calendar_start - start_arg;
               calendar_end_offset := calendar_end - end_arg;

               calendar_length := calendar_end - calendar_start;
               calendar_period_size_diff_percentage := 1.0 - (calendar_length/period_length);



               RETURN;
END
$$;


ALTER FUNCTION public.calendar_period_full(start_arg date, end_arg date, OUT calendar_period character varying, OUT calendar_year integer, OUT calendar_start_offset numeric, OUT calendar_end_offset numeric, OUT calendar_period_size_diff_percentage double precision) OWNER TO postgres;

--
-- Name: calendar_period_size_diff_percentage(date, date); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION calendar_period_size_diff_percentage(start_arg date, end_arg date) RETURNS double precision
    LANGUAGE plpgsql
    AS $$
BEGIN
               RETURN (calendar_period_full(start_arg, end_arg)).calendar_period_size_diff_percentage;
END
$$;


ALTER FUNCTION public.calendar_period_size_diff_percentage(start_arg date, end_arg date) OWNER TO postgres;

--
-- Name: calendar_start_offset(date, date); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION calendar_start_offset(start_arg date, end_arg date) RETURNS numeric
    LANGUAGE plpgsql
    AS $$
BEGIN
               RETURN (calendar_period_full(start_arg, end_arg)).calendar_start_offset;
END
$$;


ALTER FUNCTION public.calendar_start_offset(start_arg date, end_arg date) OWNER TO postgres;

--
-- Name: calendar_year(date); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION calendar_year(instant_arg date) RETURNS integer
    LANGUAGE plpgsql
    AS $$
BEGIN
               RETURN (calendar_period_full(instant_arg)).calendar_year;
END
$$;


ALTER FUNCTION public.calendar_year(instant_arg date) OWNER TO postgres;

--
-- Name: calendar_year(date, date); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION calendar_year(start_arg date, end_arg date) RETURNS integer
    LANGUAGE plpgsql
    AS $$
BEGIN
               RETURN (calendar_period_full(start_arg, end_arg)).calendar_year;
END
$$;


ALTER FUNCTION public.calendar_year(start_arg date, end_arg date) OWNER TO postgres;

--
-- Name: context_aug_trigger(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION context_aug_trigger() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
               DECLARE
                              calendar              RECORD;

               BEGIN
                              IF (TG_OP = 'DELETE') THEN
                                             --DELETE FROM context_aug WHERE context_id = OLD.context_id;
                                             --the fk contstaint will delete the context_aug record.
                                             RETURN OLD;
                              ELSEIF (TG_OP = 'UPDATE') THEN
                                             calendar := calendar_period_full(NEW);

                                             UPDATE context_aug
                                             SET fiscal_year = fiscal_year(NEW)::integer,
                                                 fiscal_period = fiscal_period(NEW),
                                                 context_hash = hash_context(NEW),
                                                 calendar_period = calendar.calendar_period,
                                                 calendar_start_offset = calendar.calendar_start_offset,
                                                 calendar_end_offset = calendar.calendar_end_offset,
                                                 calendar_year = calendar.calendar_year,
                                                 calendar_period_size_diff_percentage = calendar.calendar_period_size_diff_percentage
                                             WHERE context_id = NEW.context_id;
                                             RETURN NEW;
                              ELSEIF (TG_OP = 'INSERT') THEN
                                             calendar := calendar_period_full(NEW);

                                             INSERT INTO context_aug
                                                            ( context_id
                                                            ,fiscal_year
                                                            ,fiscal_period
                                                            ,context_hash
                                                            ,dimension_hash
                                                            ,calendar_year
                                                            ,calendar_period
                                                            ,calendar_start_offset
                                                            ,calendar_end_offset
                                                            ,calendar_period_size_diff_percentage)
                                             VALUES (NEW.context_id
                                                    ,fiscal_year(NEW)::integer
                                                    ,fiscal_period(NEW)
                                                    ,hash_context(NEW)
                                                    ,null
                                                    ,calendar.calendar_year
                                                    ,calendar.calendar_period
                                                    ,calendar.calendar_start_offset
                                                    ,calendar.calendar_end_offset
                                                    ,calendar.calendar_period_size_diff_percentage);
                                             RETURN NEW;
                              END IF;
                              RETURN NULL;
               END;
$$;


ALTER FUNCTION public.context_aug_trigger() OWNER TO postgres;

--
-- Name: crc32(text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION crc32(word text) RETURNS bigint
    LANGUAGE plpgsql IMMUTABLE
    AS $$
DECLARE tmp bigint;
DECLARE i int;
DECLARE j int;
DECLARE byte_length int;
DECLARE word_array bytea;
BEGIN
IF COALESCE(word, '') = '' THEN
return 0;
END IF;

i = 0;
tmp = 4294967295;
byte_length = bit_length(word) / 8;
word_array = decode(replace(word, E'\\\\', E'\\\\\\\\'), 'escape');
LOOP
tmp = (tmp # get_byte(word_array, i))::bigint;
i = i + 1;
j = 0;
LOOP
tmp = ((tmp >> 1) # (3988292384 * (tmp & 1)))::bigint;
j = j + 1;
IF j >= 8 THEN
EXIT;
END IF;
END LOOP;
IF i >= byte_length THEN
EXIT;
END IF;
END LOOP;
return (tmp # 4294967295);
END
$$;


ALTER FUNCTION public.crc32(word text) OWNER TO postgres;

--
-- Name: crypt(text, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION crypt(text, text) RETURNS text
    LANGUAGE c IMMUTABLE STRICT
    AS '$libdir/pgcrypto', 'pg_crypt';


ALTER FUNCTION public.crypt(text, text) OWNER TO postgres;

--
-- Name: dearmor(text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION dearmor(text) RETURNS bytea
    LANGUAGE c IMMUTABLE STRICT
    AS '$libdir/pgcrypto', 'pg_dearmor';


ALTER FUNCTION public.dearmor(text) OWNER TO postgres;

--
-- Name: decrypt(bytea, bytea, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION decrypt(bytea, bytea, text) RETURNS bytea
    LANGUAGE c IMMUTABLE STRICT
    AS '$libdir/pgcrypto', 'pg_decrypt';


ALTER FUNCTION public.decrypt(bytea, bytea, text) OWNER TO postgres;

--
-- Name: decrypt_iv(bytea, bytea, bytea, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION decrypt_iv(bytea, bytea, bytea, text) RETURNS bytea
    LANGUAGE c IMMUTABLE STRICT
    AS '$libdir/pgcrypto', 'pg_decrypt_iv';


ALTER FUNCTION public.decrypt_iv(bytea, bytea, bytea, text) OWNER TO postgres;

--
-- Name: delete_accession(bigint); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION delete_accession(in_accession_id bigint) RETURNS integer
    LANGUAGE plpgsql
    AS $$

DECLARE
  m_updated INTEGER;
  m_docs RECORD;
  m_sql TEXT;
BEGIN
	DELETE FROM fact WHERE accession_id = in_accession_id;
  	
    DELETE FROM unit_measure WHERE unit_id IN 
  			(SELECT unit_id FROM unit WHERE accession_id = in_accession_id);
  			
	DELETE FROM unit WHERE accession_id = in_accession_id;
	
	DELETE FROM context_dimension WHERE context_id IN 
			(SELECT context_id FROM context WHERE accession_id = in_accession_id);
	
	DELETE FROM context WHERE accession_id = in_accession_id;
	
	DELETE FROM relationship WHERE network_id in 
		(select network_id from network where accession_id = in_accession_id);
	
	DELETE FROM network WHERE accession_id = in_accession_id;
	
	
	FOR m_docs IN select a.document_id, count(*) c from (select document_id from accession_document_association where accession_id = in_accession_id) a
		left outer join accession_document_association b
		on a.document_id = b.document_id
		group by a.document_id LOOP
		
		--This document is not refered by any other accession. delete all related recs
		IF m_docs.c = 1 THEN
			delete from reference_part where resource_id in (select resource_id from resource where document_id = m_docs.document_id);
			delete from label_resource where resource_id in (select resource_id from resource where document_id = m_docs.document_id);
			delete from resource where document_id = m_docs.document_id;
			
			delete from reference_resource where element_id in (select element_id from element where document_id = m_docs.document_id);
			delete from element_attribute where element_id in (select element_id from element where document_id = m_docs.document_id);
			delete from element_attribute_value_association where element_id in (select element_id from element where document_id = m_docs.document_id);
			delete from element where document_id = m_docs.document_id;
		
			delete from custom_role_used_on where custom_role_type_id in (select custom_role_type_id from custom_role_type where document_id = m_docs.document_id);
			delete from custom_role_type where document_id = m_docs.document_id;
	
			delete from custom_arcrole_used_on where custom_arcrole_type_id in (select custom_arcrole_type_id from custom_arcrole_type where document_id = m_docs.document_id);
			delete from custom_arcrole_type where document_id = m_docs.document_id;
			
			delete from accession_document_association WHERE document_id = m_docs.document_id and accession_id = in_accession_id;
			delete from document where document_id = m_docs.document_id;
		END IF;
	END LOOP;
	DELETE FROM accession_document_association WHERE accession_id = in_accession_id;
	
	DELETE FROM accession WHERE accession_id = in_accession_id;
	
	m_updated = 1;
	
    RETURN m_updated;

END $$;


ALTER FUNCTION public.delete_accession(in_accession_id bigint) OWNER TO postgres;

--
-- Name: digest(text, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION digest(text, text) RETURNS bytea
    LANGUAGE c IMMUTABLE STRICT
    AS '$libdir/pgcrypto', 'pg_digest';


ALTER FUNCTION public.digest(text, text) OWNER TO postgres;

--
-- Name: digest(bytea, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION digest(bytea, text) RETURNS bytea
    LANGUAGE c IMMUTABLE STRICT
    AS '$libdir/pgcrypto', 'pg_digest';


ALTER FUNCTION public.digest(bytea, text) OWNER TO postgres;

--
-- Name: document_type(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION document_type(integer) RETURNS character varying
    LANGUAGE sql
    AS $_$
/* This function determines the SEC document type for a given filing. I takes an accession_id as the parameter.
*/
               SELECT f.fact_value
               FROM   fact f
                 JOIN accession a
                   ON f.accession_id = a.accession_id
                 JOIN element e
                   ON f.element_id = e.element_id
                 JOIN qname qe
                   ON e.qname_id = qe.qname_id
                 JOIN namespace n
                   on qe.namespace = n.uri
               WHERE qe.local_name = 'DocumentType'
               AND   n.prefix = 'dei'
               AND   a.accession_id = $1
$_$;


ALTER FUNCTION public.document_type(integer) OWNER TO postgres;

--
-- Name: encrypt(bytea, bytea, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION encrypt(bytea, bytea, text) RETURNS bytea
    LANGUAGE c IMMUTABLE STRICT
    AS '$libdir/pgcrypto', 'pg_encrypt';


ALTER FUNCTION public.encrypt(bytea, bytea, text) OWNER TO postgres;

--
-- Name: encrypt_iv(bytea, bytea, bytea, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION encrypt_iv(bytea, bytea, bytea, text) RETURNS bytea
    LANGUAGE c IMMUTABLE STRICT
    AS '$libdir/pgcrypto', 'pg_encrypt_iv';


ALTER FUNCTION public.encrypt_iv(bytea, bytea, bytea, text) OWNER TO postgres;

--
-- Name: extension_element_hash_string(integer, character varying); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION extension_element_hash_string(entity_id_arg integer, element_local_name character varying) RETURNS character varying
    LANGUAGE plpgsql
    AS $$

BEGIN
	RETURN 'x' || entity_id_arg || ':' ||element_local_name;
END

$$;


ALTER FUNCTION public.extension_element_hash_string(entity_id_arg integer, element_local_name character varying) OWNER TO postgres;

--
-- Name: extension_element_id(integer, character varying); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION extension_element_id(entity_id_arg integer, element_local_name character varying) RETURNS integer
    LANGUAGE plpgsql
    AS $$
DECLARE
	element_id_ret integer;
BEGIN

	SELECT min(e.element_id)
	INTO element_id_ret	
	FROM fact f
	JOIN element e
	  ON f.element_id = e.element_id
	JOIN accession a
	  ON f.accession_id = a.accession_id
	JOIN qname q
	  ON e.qname_id = q.qname_id
	WHERE a.entity_id = entity_id_arg
	  AND q.local_name = element_local_name
	  AND NOT EXISTS (
		SELECT 1
		FROM namespace n
		WHERE q.local_name = n.uri
		  AND n.is_base = true)

	UNION
	SELECT min(e.element_id)
	FROM element e
	JOIN qname q
	  ON e.qname_id = q.qname_id
	JOIN context_dimension cd
	  ON e.qname_id = cd.dimension_qname_id
	JOIN context c
	  ON cd.context_id = c.context_id
	JOIN accession a
	  ON c.accession_id = a.accession_id
	WHERE a.entity_id = entity_id_arg
	  AND q.local_name = element_local_name
	  AND NOT EXISTS (
		SELECT 1
		FROM namespace n
		WHERE q.local_name = n.uri
		  AND n.is_base = true)
	  
	UNION
	SELECT min(e.element_id)
	FROM element e
	JOIN qname q
	  ON e.qname_id = q.qname_id
	JOIN context_dimension cd
	  ON e.qname_id = cd.member_qname_id
	JOIN context c
	  ON cd.context_id = c.context_id
	JOIN accession a
	  ON c.accession_id = a.accession_id
	WHERE a.entity_id = entity_id_arg
	  AND q.local_name = element_local_name
	  AND NOT EXISTS (
		SELECT 1
		FROM namespace n
		WHERE q.local_name = n.uri
		  AND n.is_base = true)

	ORDER BY 1;		  

	RETURN element_id_ret;
END
$$;


ALTER FUNCTION public.extension_element_id(entity_id_arg integer, element_local_name character varying) OWNER TO postgres;

--
-- Name: fact_aug_trigger(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION fact_aug_trigger() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
               fact_hash_string bytea;
               calendar_hash_string bytea;
BEGIN
	IF (TG_OP = 'DELETE') THEN
		SELECT fact_hash INTO fact_hash_string FROM fact_aug WHERE fact_id = OLD.fact_id;
		SELECT calendar_hash INTO calendar_hash_string FROM fact_aug WHERE fact_id = OLD.fact_id;

		DELETE FROM fact_aug WHERE fact_id = OLD.fact_id;
		PERFORM calc_fact_aug(fact_hash_string);
		PERFORM calc_calendar_ultimus(calendar_hash_string);

		RETURN OLD;

	ELSEIF (TG_OP = 'UPDATE' OR TG_OP = 'INSERT') THEN
		PERFORM update_fact_aug_by_fact(NEW.fact_id);
		-- add the uom
		UPDATE fact_aug
		SET uom = uom(NEW.unit_id)
		WHERE fact_id = NEW.fact_id;

		RETURN NEW;

	END IF;
	RETURN NULL;
END;
$$;


ALTER FUNCTION public.fact_aug_trigger() OWNER TO postgres;

--
-- Name: fact_hash_2_calendar(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION fact_hash_2_calendar(fact_id_arg integer) RETURNS character varying
    LANGUAGE plpgsql
    AS $$

DECLARE

               calendar_hash_ret character varying;

BEGIN



               SELECT fact_hash_2_calendar(hash_fact_string(fact_id_arg))

               INTO calendar_hash_ret

               FROM fact_aug

               WHERE fact_id = fact_id_arg;



               RETURN calendar_hash_ret;

END

$$;


ALTER FUNCTION public.fact_hash_2_calendar(fact_id_arg integer) OWNER TO postgres;

--
-- Name: fact_hash_2_calendar(character varying); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION fact_hash_2_calendar(fact_hash_arg character varying) RETURNS character varying
    LANGUAGE plpgsql
    AS $$
DECLARE
               hash_array character varying[];
               period_start        date;
               period_end         date;
               period_instant    date;
BEGIN

               hash_array := string_to_array(fact_hash_arg, '|');

               CASE
                              WHEN hash_array[3] = 'F' THEN
                                             RETURN null;
                              WHEN strpos(hash_array[3],'-') <> 0 THEN
                                             period_start := to_date(split_part(hash_array[3],'-',1),'yyyymmdd');
                                             period_end := to_date(split_part(hash_array[3],'-',2),'yyyymmdd');
                                             IF strpos(calendar_period(period_start, period_end),'-') > 0 THEN
                                                            RETURN null;
                                             ELSE
                                                            hash_array[3] := calendar_period(period_start, period_end) || calendar_year(period_start, period_end);
                                             END IF;
                              ELSE
                                             period_instant := to_date(hash_array[3],'yyyymmdd');
                                             IF strpos(calendar_period(period_instant),'-') > 0 THEN
                                                            RETURN null;
                                             ELSE
                                                            hash_array[3] := calendar_period(period_instant) || calendar_year(period_instant);
                                             END IF;
               END CASE;
               RETURN array_to_string(hash_array,'|');
END
$$;


ALTER FUNCTION public.fact_hash_2_calendar(fact_hash_arg character varying) OWNER TO postgres;

--
-- Name: fiscal_period(context); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION fiscal_period(context_arg context) RETURNS character varying
    LANGUAGE plpgsql
    AS $$
BEGIN
               if context_arg.period_instant is not null then
                              return fiscal_period(context_arg.period_instant, context_arg.accession_id);
               else
                              return fiscal_period(context_arg.period_start, context_arg.period_end, context_arg.accession_id);
               end if;
END
$$;


ALTER FUNCTION public.fiscal_period(context_arg context) OWNER TO postgres;

--
-- Name: fiscal_period(date, date); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION fiscal_period(instant_arg date, year_end_date date) RETURNS character varying
    LANGUAGE plpgsql
    AS $$
-- returns the fisal period based on an instant date and the month and day of the year end.
DECLARE
               date_diff integer;
BEGIN
               date_diff := year_end_date - instant_arg;
               RETURN CASE
                                             WHEN date_diff >= 263 AND date_diff <= 283 THEN '1Q'
                                             WHEN date_diff >= 172 AND date_diff <= 192 THEN '2Q'
                                             WHEN date_diff >= 81 AND date_diff <= 101 THEN '3Q'
                                             WHEN date_diff >= -10 AND date_diff <= 10 THEN 'Y'
                                             ELSE to_char(instant_arg,'yyyy-mm-dd')
                              END;
END
$$;


ALTER FUNCTION public.fiscal_period(instant_arg date, year_end_date date) OWNER TO postgres;

--
-- Name: fiscal_period(date, integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION fiscal_period(instant_arg date, accession_id_arg integer) RETURNS character varying
    LANGUAGE plpgsql
    AS $$
-- Returns the fiscal period for an instant date and the accession id
DECLARE
end_month_day character varying;
end_month_num integer;
end_day_num integer;
year_end double precision;

BEGIN
select fiscal_year_end_adjusted(accession_id_arg) into end_month_day;
select substring(end_month_day,E'--([^\\-]*)') into end_month_num;
select substring(end_month_day,E'--[^\\-]*-(.*)') into end_day_num;
select fiscal_year (instant_arg, accession_id_arg) into year_end;

return fiscal_period(instant_arg, date(lpad((year_end - fiscal_year_beginning_of_year_adjustment(end_month_num, end_day_num))::varchar,4,'0')|| '-' ||end_month_num ||'-'|| end_day_num));
END
$$;


ALTER FUNCTION public.fiscal_period(instant_arg date, accession_id_arg integer) OWNER TO postgres;

--
-- Name: fiscal_period(date, integer, integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION fiscal_period(instant date, month_num integer, day_num integer) RETURNS character varying
    LANGUAGE plpgsql
    AS $$
-- returns the fisal period based on an instandate date and the month and day of the year end.
DECLARE
year_end_date date;
BEGIN
select date(lpad((fiscal_year(instant, month_num, day_num) - fiscal_year_beginning_of_year_adjustment(month_num, day_num))::varchar,4,'0')||'-'||month_num||'-'||day_num) into year_end_date;
return fiscal_period (instant, year_end_date);

END
$$;


ALTER FUNCTION public.fiscal_period(instant date, month_num integer, day_num integer) OWNER TO postgres;

--
-- Name: fiscal_period(date, date, date); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION fiscal_period(start_date date, end_date date, year_end_date date) RETURNS character varying
    LANGUAGE plpgsql
    AS $_$
-- Returns the fiscal period for a duration (start and end date) and a fiscal year end date
DECLARE
               period_length     integer;
               end_date_period character varying;
BEGIN
               period_length := end_date - start_date;
               end_date_period := fiscal_period (end_date, year_end_date);
--            IF end_date_period = 'Unknown' THEN
--                           RETURN 'Unknown';
               IF end_date_period ~ E'\\d$' THEN
                              RETURN to_char(start_date,'yyyy-mm-dd') || ' - ' || to_char(end_date,'yyyy-mm-dd');
               ELSE

                              RETURN CASE
                                             -- quarters
                                             WHEN period_length >= 81 AND period_length <= 101 THEN
                                                            CASE WHEN end_date_period = 'Y' THEN '4Q' ELSE end_date_period END
                                             -- halves
                                             WHEN period_length >= 172 AND period_length <= 192 THEN
                                                            CASE WHEN end_date_period = '2Q' THEN '1H'
                                                                 WHEN end_date_period = 'Y' THEN '2H'
                                                                 ELSE to_char(start_date,'yyyy-mm-dd') || ' - ' || to_char(end_date,'yyyy-mm-dd')
                                                            END
                                             --3Q CUM
                                             WHEN period_length >= 263 AND period_length <= 283 and end_date_period = '3Q' THEN '3QCUM'
                                             -- year
                                             WHEN period_length >= 355 AND period_length <= 375 AND end_date_period = 'Y' THEN 'Y'
                                             -- otherwise the period is unknown
                                             ELSE to_char(start_date,'yyyy-mm-dd') || ' - ' || to_char(end_date,'yyyy-mm-dd')
                                     END;

               END IF;
END
$_$;


ALTER FUNCTION public.fiscal_period(start_date date, end_date date, year_end_date date) OWNER TO postgres;

--
-- Name: fiscal_period(date, date, integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION fiscal_period(start_date date, end_date date, accession_id_arg integer) RETURNS character varying
    LANGUAGE plpgsql
    AS $$
-- Returns the fiscal period for a duration (start and end date) and the accession id
DECLARE
end_month_day character varying;
end_month_num integer;
end_day_num integer;

BEGIN
select fiscal_year_end_adjusted(accession_id_arg) into end_month_day;
select substring(end_month_day,E'--([^\\-]*)') into end_month_num;
select substring(end_month_day,E'--[^\\-]*-(.*)') into end_day_num;

return fiscal_period(start_date, end_date, end_month_num, end_day_num);
END
$$;


ALTER FUNCTION public.fiscal_period(start_date date, end_date date, accession_id_arg integer) OWNER TO postgres;

--
-- Name: fiscal_period(date, date, integer, integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION fiscal_period(start_date date, end_date date, month_num integer, day_num integer) RETURNS character varying
    LANGUAGE plpgsql
    AS $$
-- returns the fisal period based on a duration and the month and day of the year end.
DECLARE
year_end_date date;
BEGIN
select date(lpad((fiscal_year(end_date, month_num, day_num) - fiscal_year_beginning_of_year_adjustment(month_num, day_num))::varchar,4,'0')||'-'||month_num||'-'||day_num) into year_end_date;
return fiscal_period (start_date, end_date, year_end_date);

END
$$;


ALTER FUNCTION public.fiscal_period(start_date date, end_date date, month_num integer, day_num integer) OWNER TO postgres;

--
-- Name: fiscal_year(context); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION fiscal_year(context_arg context) RETURNS character varying
    LANGUAGE plpgsql
    AS $$
BEGIN
               if context_arg.period_instant is not null then
                              return fiscal_year(context_arg.period_instant, context_arg.accession_id);
               else
                              return fiscal_year(context_arg.period_end, context_arg.accession_id);
               end if;
END
$$;


ALTER FUNCTION public.fiscal_year(context_arg context) OWNER TO postgres;

--
-- Name: fiscal_year(date, integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION fiscal_year(reporting_date_arg date, accession_id_arg integer) RETURNS double precision
    LANGUAGE plpgsql
    AS $$
--Returns the fiscal year for a given reporting date and an accession id
DECLARE
               end_date varchar;
               month_num integer;
               day_num integer;
BEGIN
               select fiscal_year_end(accession_id_arg) into end_date;
               select substring(end_date,E'--([^\\-]*)') into month_num;
               select substring(end_date,E'--[^\\-]*-(.*)') into day_num;
               return fiscal_year (reporting_date_arg, month_num, day_num);
END
$$;


ALTER FUNCTION public.fiscal_year(reporting_date_arg date, accession_id_arg integer) OWNER TO postgres;

--
-- Name: fiscal_year(date, date); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION fiscal_year(date, date) RETURNS double precision
    LANGUAGE sql
    AS $_$
               SELECT fiscal_year($1,date_part('month',$2)::integer,date_part('day',$2)::integer)
$_$;


ALTER FUNCTION public.fiscal_year(date, date) OWNER TO postgres;

--
-- Name: fiscal_year(date, integer, integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION fiscal_year(cur_date date, month_num integer, day_num integer) RETURNS double precision
    LANGUAGE plpgsql
    AS $$
-- Determine the fiscal year based on a period date and the month/day year end.
DECLARE
               adjusted_date date;
               beginning_year_adjustment integer;
               result_year_end double precision;
BEGIN
               /* Adjust the date by 10 days. If the date is 10 days over the month/day end it is considered
                  part the prior fiscal year. This happens when the month/day year end falls on a weekend or
                  for fiscal years that are based on 52 weeks.
               */
               SELECT cur_date - 10 INTO adjusted_date;

               /* The adjustement is made if the year end is in the very begining of the calendar year.
                  If the year end is jan 3 and our date is 2010-1-3, which is the year end, we will still think of
                  the fiscal year as 2009
               */
               beginning_year_adjustment := fiscal_year_beginning_of_year_adjustment(month_num, day_num);

               SELECT
                              CASE
                                             WHEN month_num is null or day_num is null
                                             -- return the year of the cur_date, but adjust for beginning of year issues.
                                                            THEN date_part('year',cur_date) + beginning_year_adjustment
                                             -- This tests that the month and day are a valid combintaiton. If they are not, the date conversion will fail.
                                             WHEN NOT is_date('2000-'||month_num||'-'||day_num)
                                                            THEN date_part('year',cur_date) + beginning_year_adjustment
                                             -- The cur month/day is after the year end month/dat, so add one the year.
                                             WHEN ((date_part('month',adjusted_date) * 100) + date_part('day',adjusted_date)) > month_num * 100 + day_num
                                                            THEN date_part('year',adjusted_date) + 1 + beginning_year_adjustment
                                             ELSE date_part('year',adjusted_date) + beginning_year_adjustment
                              END INTO result_year_end;
               RETURN result_year_end;
END
$$;


ALTER FUNCTION public.fiscal_year(cur_date date, month_num integer, day_num integer) OWNER TO postgres;

--
-- Name: fiscal_year_beginning_of_year_adjustment(integer, integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION fiscal_year_beginning_of_year_adjustment(month_num integer, day_num integer) RETURNS integer
    LANGUAGE plpgsql
    AS $$
BEGIN
               IF month_num = 1 and day_num <=10
                              THEN RETURN -1;
                              ELSE RETURN 0;
               END IF;
END
$$;


ALTER FUNCTION public.fiscal_year_beginning_of_year_adjustment(month_num integer, day_num integer) OWNER TO postgres;

--
-- Name: fiscal_year_end(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION fiscal_year_end(accession_id_arg integer) RETURNS character varying
    LANGUAGE plpgsql
    AS $$
-- Gets the Month and Day of the fiscal year end for the filing. The parameter is the accession_id.
DECLARE
               fact_row fact%ROWTYPE;
               end_date varchar;
               entity_id_for_accession integer;
               filing_date_for_accession date;
BEGIN
               -- get the fiscal year end month/day for the accession
               SELECT f.*
               INTO fact_row
               FROM   fact f
                 JOIN element e
                   ON f.element_id = e.element_id
                 JOIN qname qe
                   ON e.qname_id = qe.qname_id
                 JOIN namespace n
                   ON qe.namespace = n.uri
               WHERE qe.local_name = 'CurrentFiscalYearEndDate'
                 AND  n.prefix = 'dei'
                 AND  f.accession_id = accession_id_arg;

               -- if the fiscal year end month/day is not reported for the accession, then find for the most recent previous accession
               if fact_row is null then
                 SELECT entity_id
                       ,filing_date
                 INTO   entity_id_for_accession
                       ,filing_date_for_accession
                 FROM accession
                 WHERE accession_id = accession_id_arg;

                 SELECT f.*
                 INTO fact_row
                 FROM   fact f
                 JOIN element e
                   ON f.element_id = e.element_id
                 JOIN qname qe
                   ON e.qname_id = qe.qname_id
                 JOIN accession a
                   ON f.accession_id = a.accession_id
                 JOIN namespace n
                   ON qe.namespace = n.uri
                 WHERE qe.local_name = 'CurrentFiscalYearEndDate'
                   AND n.prefix = 'dei'
                   AND a.entity_id = entity_id_for_accession
                 --  AND a.filing_date < filing_date_for_accession
                 --ORDER BY filing_date DESC;
                 ORDER BY CASE WHEN filing_date_for_accession >= a.filing_date THEN 0 ELSE 1 END
                          ,abs(filing_date_for_accession - a.filing_date);

               end if;

               return fact_row.fact_value;
END
$$;


ALTER FUNCTION public.fiscal_year_end(accession_id_arg integer) OWNER TO postgres;

--
-- Name: fiscal_year_end(character varying); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION fiscal_year_end(filing_accession_number_arg character varying) RETURNS character varying
    LANGUAGE plpgsql
    AS $$
-- Gets the Month and Day of the fiscal year end for the filing. The parameter is the filing accession number.
DECLARE
               accession_id_var integer;
BEGIN
               select accession_id into accession_id_var
               from   accession
               where  filing_accession_number = filing_accession_number_arg;

               return fiscal_year_end(accession_id_var);
END
$$;


ALTER FUNCTION public.fiscal_year_end(filing_accession_number_arg character varying) OWNER TO postgres;

--
-- Name: fiscal_year_end_adjusted(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION fiscal_year_end_adjusted(accession_id_arg integer) RETURNS character varying
    LANGUAGE plpgsql
    AS $$
-- Gets the Month and Day of the fiscal year end for the filing. The parameter is the accession_id.
DECLARE
fiscal_year_end_var varchar;
BEGIN
SELECT fiscal_year_end(accession_id_arg) INTO fiscal_year_end_var;

IF fiscal_year_end_var = '--02-29' or fiscal_year_end_var = '--2-29' THEN
fiscal_year_end_var := '--02-28';
END IF;

RETURN fiscal_year_end_var;
END
$$;


ALTER FUNCTION public.fiscal_year_end_adjusted(accession_id_arg integer) OWNER TO postgres;

--
-- Name: fix_fact_aug(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION fix_fact_aug(fact_id_arg integer) RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
	hash_string	varchar;
BEGIN
	RAISE INFO 'Processing: (%)', fact_id_arg;
	hash_string = hash_fact(fact_id_arg);
	UPDATE fact_aug
	SET fact_hash=hash_fact(hash_string),
	    calendar_hash=hash_fact(fact_hash_2_calendar(hash_string))
	WHERE fact_id = fact_id_arg;
END
$$;


ALTER FUNCTION public.fix_fact_aug(fact_id_arg integer) OWNER TO postgres;

--
-- Name: gen_random_bytes(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION gen_random_bytes(integer) RETURNS bytea
    LANGUAGE c STRICT
    AS '$libdir/pgcrypto', 'pg_random_bytes';


ALTER FUNCTION public.gen_random_bytes(integer) OWNER TO postgres;

--
-- Name: gen_salt(text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION gen_salt(text) RETURNS text
    LANGUAGE c STRICT
    AS '$libdir/pgcrypto', 'pg_gen_salt';


ALTER FUNCTION public.gen_salt(text) OWNER TO postgres;

--
-- Name: gen_salt(text, integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION gen_salt(text, integer) RETURNS text
    LANGUAGE c STRICT
    AS '$libdir/pgcrypto', 'pg_gen_salt_rounds';


ALTER FUNCTION public.gen_salt(text, integer) OWNER TO postgres;

--
-- Name: get_entity_id_by_element(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION get_entity_id_by_element(element_id_arg integer) RETURNS integer
    LANGUAGE plpgsql
    AS $$
DECLARE
	return_int integer;
BEGIN
	SELECT MAX(a.entity_id)
	INTO return_int
	FROM accession_element ae
	JOIN accession a
	 ON (ae.accession_id = a.accession_id)
	WHERE ae.element_id = element_id_arg;

	RETURN return_int;
END
$$;


ALTER FUNCTION public.get_entity_id_by_element(element_id_arg integer) OWNER TO postgres;

--
-- Name: hash_context(context); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION hash_context(context_arg context) RETURNS bytea
    LANGUAGE plpgsql
    AS $$

BEGIN
	RETURN digest(hash_context_string(context_arg),'sha224');

END

$$;


ALTER FUNCTION public.hash_context(context_arg context) OWNER TO postgres;

--
-- Name: hash_context(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION hash_context(context_id_arg integer) RETURNS bytea
    LANGUAGE plpgsql
    AS $$

BEGIN

	RETURN digest(hash_context_string(context_id_arg),'sha224');

END

$$;


ALTER FUNCTION public.hash_context(context_id_arg integer) OWNER TO postgres;

--
-- Name: hash_context_string(context); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION hash_context_string(context_arg context) RETURNS character varying
    LANGUAGE plpgsql
    AS $$

DECLARE

               hash_string character varying;

               entity_id_var integer;
               dim_hash character varying;

BEGIN



               -- initialize the hash

               hash_string := '';



               -- Get entity id from the accession table

               SELECT entity_id INTO entity_id_var FROM accession WHERE accession_id = context_arg.accession_id;



               -- add entity id.

               hash_string :=  hash_string || entity_id_var;



               -- add entity (using entity_id)

               IF context_arg.period_start IS NULL AND context_arg.period_end IS NULL AND context_arg.period_instant IS NULL THEN

                              hash_string := hash_string || '|' || 'F';

               ELSIF context_arg.period_start IS NULL THEN

                              hash_string := hash_string || '|' || to_char(context_arg.period_instant,'YYYYMMDD');

               ELSE

                              hash_string := hash_string || '|' || to_char(context_arg.period_start,'YYYYMMDD') || '-' || to_char(context_arg.period_end,'YYYYMMDD');

               END IF;


	       -- add dimensional qualifications
	       SELECT hash_dimensional_qualifications(context_arg.context_id) INTO dim_hash;
	       IF dim_hash <> '' THEN
			hash_string := hash_string || '|' || dim_hash;
	       END IF;


               RETURN hash_string;

END

$$;


ALTER FUNCTION public.hash_context_string(context_arg context) OWNER TO postgres;

--
-- Name: hash_context_string(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION hash_context_string(context_id_arg integer) RETURNS character varying
    LANGUAGE plpgsql
    AS $$

DECLARE

               hash_string character varying;

BEGIN



               SELECT hash_context_string(c.*)

               INTO hash_string

               FROM context c

               WHERE c.context_id = context_id_arg;



               RETURN hash_string;



END

$$;


ALTER FUNCTION public.hash_context_string(context_id_arg integer) OWNER TO postgres;

--
-- Name: hash_dimensional_qualifications(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION hash_dimensional_qualifications(context_id_arg integer) RETURNS character varying
    LANGUAGE plpgsql
    AS $$
DECLARE
	dimension_hash character varying;
	cd_record RECORD;
	is_first boolean;
	BEGIN
	dimension_hash := '';
	is_first := true;

	FOR cd_record IN 
		SELECT cd.dimension_qname_id
		       ,cd.member_qname_id
		       ,a.entity_id
		       ,CASE WHEN COALESCE(nd.is_base,false) = false THEN extension_element_hash_string(a.entity_id, qd.local_name) ELSE base_element_hash_string(qd.namespace, qd.local_name) END AS dimension_hash_id
		       ,CASE WHEN COALESCE(nm.is_base,false) = false THEN extension_element_hash_string(a.entity_id, qm.local_name) ELSE base_element_hash_string(qm.namespace, qm.local_name) END AS member_hash_id

		FROM context_dimension cd
		JOIN context c
		   ON cd.context_id = c.context_id
		JOIN accession a
		   ON c.accession_id = a.accession_id
		JOIN qname qd
		   ON cd.dimension_qname_id = qd.qname_id
		JOIN qname qm
		   ON cd.member_qname_id = qm.qname_id
		LEFT JOIN namespace nd
		   ON qd.namespace = nd.uri
		LEFT JOIN namespace nm
		   ON qm.namespace = nm.uri
		WHERE cd.context_id = context_id_arg
		   AND cd.is_default = false
		   AND c.specifies_dimensions = true
		ORDER BY dimension_qname_id, member_qname_id
		LOOP
		IF is_first THEN
		is_first := false;
		ELSE
		dimension_hash := dimension_hash || '|';
		END IF;
		dimension_hash := dimension_hash || cd_record.dimension_hash_id || '.' || cd_record.member_hash_id ;
	END LOOP;

RETURN dimension_hash;

END
$$;


ALTER FUNCTION public.hash_dimensional_qualifications(context_id_arg integer) OWNER TO postgres;

--
-- Name: hash_dimensional_qualifications(context); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION hash_dimensional_qualifications(context_arg context) RETURNS character varying
    LANGUAGE plpgsql
    AS $$
BEGIN
               RETURN hash_dimensional_qualifications(context_arg.context_id);
END
$$;


ALTER FUNCTION public.hash_dimensional_qualifications(context_arg context) OWNER TO postgres;

--
-- Name: hash_dimensional_qualifications_for_fact(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION hash_dimensional_qualifications_for_fact(fact_id_arg integer) RETURNS character varying
    LANGUAGE plpgsql
    AS $$
DECLARE
context_id_var integer;
dimension_hash character varying;
cd_record RECORD;
BEGIN

SELECT hash_dimensional_qualifications(context_id) INTO dimension_hash FROM fact WHERE fact_id = fact_id_arg;
/*

dimension_hash := '';

FOR cd_record IN SELECT *
 FROM context_dimension
WHERE context_id = context_id_var
   AND is_default = false
ORDER BY dimension_qname_id, member_qname_id
LOOP
dimension_hash := dimension_hash || '|' || cd_record.dimension_qname_id || '.' || cd_record.member_qname_id || '|';
END LOOP;
*/
RETURN dimension_hash;

END
$$;


ALTER FUNCTION public.hash_dimensional_qualifications_for_fact(fact_id_arg integer) OWNER TO postgres;

--
-- Name: hash_dimensional_qualifications_test(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION hash_dimensional_qualifications_test(context_id_arg integer) RETURNS character varying
    LANGUAGE plpgsql
    AS $$
DECLARE
               dimension_hash character varying;
               cd_record RECORD;
               is_first boolean;
BEGIN
               dimension_hash := '';
               is_first := true;

               FOR cd_record IN SELECT cd.dimension_qname_id
                                                    ,cd.member_qname_id
                                                    ,a.entity_id
                                                    ,CASE WHEN COALESCE(nd.is_base,false) = false THEN extension_element_id(a.entity_id, qd.local_name) ELSE ed.element_id END AS dimension_hash_id
                                                    ,CASE WHEN COALESCE(nm.is_base,false) = false THEN extension_element_id(a.entity_id, qm.local_name) ELSE em.element_id END AS member_hash_id

                                             FROM context_dimension cd
                                             JOIN context c
                                                ON cd.context_id = c.context_id
                                             JOIN accession a
                                                ON c.accession_id = a.accession_id
                                             JOIN qname qd
                                                ON cd.dimension_qname_id = qd.qname_id
                                             JOIN qname qm
                                                ON cd.member_qname_id = qm.qname_id
                                             JOIN element ed
                                                ON qd.qname_id = ed.qname_id
                                             JOIN element em
                                                ON qm.qname_id = em.qname_id
                                             LEFT JOIN namespace nd
                                                ON qd.namespace = nd.uri
                                             LEFT JOIN namespace nm
                                                ON qm.namespace = nm.uri
                                             WHERE cd.context_id = context_id_arg
                                                AND cd.is_default = false
                                                AND c.specifies_dimensions = true
                                             ORDER BY dimension_qname_id, member_qname_id
               LOOP
                              IF is_first THEN
                                             is_first := false;
                              ELSE
                                             dimension_hash := dimension_hash || '|';
                              END IF;
                              dimension_hash := dimension_hash || cd_record.dimension_hash_id || '.' || cd_record.member_hash_id ;
               END LOOP;

               RETURN dimension_hash;

END
$$;


ALTER FUNCTION public.hash_dimensional_qualifications_test(context_id_arg integer) OWNER TO postgres;

--
-- Name: hash_fact(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION hash_fact(fact_id_arg integer) RETURNS bytea
    LANGUAGE plpgsql
    AS $$

BEGIN
	RETURN digest(hash_fact_string(fact_id_arg),'sha224');

END

$$;


ALTER FUNCTION public.hash_fact(fact_id_arg integer) OWNER TO postgres;

--
-- Name: hash_fact(character varying); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION hash_fact(hash_string character varying) RETURNS bytea
    LANGUAGE plpgsql
    AS $$

BEGIN
	RETURN digest(hash_string,'sha224');

END

$$;


ALTER FUNCTION public.hash_fact(hash_string character varying) OWNER TO postgres;

--
-- Name: hash_fact_string(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION hash_fact_string(fact_id_arg integer) RETURNS character varying
    LANGUAGE plpgsql
    AS $$

DECLARE

               hash_string character varying;

               f_rec RECORD;

               e_rec RECORD;

               dimension_hash character varying;

BEGIN

/* This function will hash all of the meta data about a fact (unit, period, entity, dimensional qualifications).

   The hash is composed of components separated by '|' character. The components are (in order):

               element identifier

               entity_id

               period

               unit

               dimensional qualifications if any



   The hash does not handle further qualifications in the <xbrli:scenario> or <xbrli:segment> elements.

*/

               -- initialize the hash

               hash_string := '';



               -- Get fact info

               SELECT f.fact_id

                      ,uom(f.unit_id) as uom

                      ,a.entity_id

                      ,c.context_id

                      ,c.period_start

                      ,c.period_end

                      ,c.period_instant

                      ,q.local_name

                      ,CASE WHEN COALESCE(n.is_base,false) = false THEN extension_element_hash_string(a.entity_id, q.local_name) ELSE base_element_hash_string(q.namespace, q.local_name)::varchar END AS element_id

               INTO f_rec

               FROM fact f

               JOIN context c

                 ON f.context_id = c.context_id

               JOIN accession a

                 ON f.accession_id = a.accession_id

               JOIN element e

                 ON f.element_id = e.element_id

               JOIN qname q

                 ON e.qname_id = q.qname_id

               LEFT JOIN namespace n

                 ON q.namespace = n.uri

               WHERE f.fact_id = fact_id_arg;



               -- element id.

               -- If the element is in the base taxonomy, the element_id is used. If the element is an extension,

               -- then element_id for the first occurrance of element for the entity is used. This is handled in the query.

               hash_string := hash_string || f_rec.element_id;





               -- add entity id.

               hash_string :=  hash_string || '|' || f_rec.entity_id;





               -- add period

               IF f_rec.period_start IS NULL AND f_rec.period_end IS NULL AND f_rec.period_instant IS NULL THEN

                              hash_string := hash_string || '|' || 'F';

               ELSIF f_rec.period_start IS NULL THEN

                              hash_string := hash_string || '|' || to_char(f_rec.period_instant,'YYYYMMDD');

               ELSE

                              hash_string := hash_string || '|' || to_char(f_rec.period_start,'YYYYMMDD') || '-' || to_char(f_rec.period_end,'YYYYMMDD');

               END IF;



               -- unit (using UOM)

               IF f_rec.uom IS NULL THEN

                              hash_string := hash_string || '|';

               ELSE

                              hash_string := hash_string || '|' || f_rec.uom;

               END IF;



               -- add the dimensional hash

               dimension_hash := hash_dimensional_qualifications(f_rec.context_id);

               IF dimension_hash != '' THEN

                              hash_string := hash_string || '|' || dimension_hash ;

               END IF;



               RETURN hash_string;





END

$$;


ALTER FUNCTION public.hash_fact_string(fact_id_arg integer) OWNER TO postgres;

--
-- Name: hmac(text, text, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION hmac(text, text, text) RETURNS bytea
    LANGUAGE c IMMUTABLE STRICT
    AS '$libdir/pgcrypto', 'pg_hmac';


ALTER FUNCTION public.hmac(text, text, text) OWNER TO postgres;

--
-- Name: hmac(bytea, bytea, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION hmac(bytea, bytea, text) RETURNS bytea
    LANGUAGE c IMMUTABLE STRICT
    AS '$libdir/pgcrypto', 'pg_hmac';


ALTER FUNCTION public.hmac(bytea, bytea, text) OWNER TO postgres;

--
-- Name: hold_xucc_for_accession(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION hold_xucc_for_accession(accession_id_arg integer) RETURNS character varying
    LANGUAGE plpgsql
    AS $$
DECLARE
             last_count          integer;
             result_id_var     integer;
             message_id_var             integer;
BEGIN
             SELECT count(*)
             INTO last_count
             FROM xuscc.consistency_check_result
             WHERE accession_id = accession_id_arg;
 
             IF last_count = 0 THEN
                           INSERT INTO xuscc.consistency_check_result (consistency_check_result_id, accession_id, run_date)
                                        VALUES (nextval('xuscc.seq_consistency_check_result'::regclass), accession_id_arg, now()) 
                                        RETURNING consistency_check_result_id INTO result_id_var;
 
                           INSERT INTO xuscc.consistency_check_message (consistency_check_message_id, consistency_check_result_id, severity, error_code, line_number, column_number)
                                       VALUES (nextval('xuscc.seq_consistency_check_message'::regclass), result_id_var, 'HOLD', 'xucc.redirector.Hold', -1, -1)
                                        RETURNING consistency_check_message_id INTO message_id_var;
 
                           INSERT INTO xuscc.consistency_check_detail (consistency_check_detail_id, consistency_check_message_id, detail)
                                        VALUES (nextval('xuscc.seq_consistency_check_detail'::regclass), message_id_var, 'Filing put on hold');
 
                           RETURN 'Added result record';
             ELSE
                           RETURN 'Result already exists';
             END IF;
END
$$;


ALTER FUNCTION public.hold_xucc_for_accession(accession_id_arg integer) OWNER TO postgres;

--
-- Name: insert_extension_namespace(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION insert_extension_namespace() RETURNS integer
    LANGUAGE plpgsql
    AS $$
DECLARE
               inserted_rows integer;
BEGIN
               INSERT INTO namespace (uri, is_base, taxonomy_version_id, "name")
               SELECT DISTINCT q.namespace, false, base_taxonomy_version(max(ada.accession_id)), 'extension'
               FROM qname q
               JOIN element e
                 USING (qname_id)
               JOIN accession_document_association ada
                 USING (document_id)
               WHERE NOT EXISTS
               (SELECT 1
               FROM namespace n1
               WHERE n1.uri = q.namespace)
               GROUP BY 1;

               GET DIAGNOSTICS inserted_rows = ROW_COUNT;

               RETURN inserted_rows;
END
$$;


ALTER FUNCTION public.insert_extension_namespace() OWNER TO postgres;

--
-- Name: is_base(character varying); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION is_base(namespace_arg character varying) RETURNS boolean
    LANGUAGE plpgsql
    AS $$
DECLARE
               namespace_row RECORD;
BEGIN
               SELECT * INTO namespace_row FROM namespace WHERE uri = namespace_arg;
               IF namespace_row.is_base THEN
                              RETURN true;
               ELSE
                              RETURN false;
               END IF;
END
$$;


ALTER FUNCTION public.is_base(namespace_arg character varying) OWNER TO postgres;

--
-- Name: is_date(character varying); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION is_date(check_date character varying) RETURNS boolean
    LANGUAGE plpgsql
    AS $$
DECLARE
               check_month integer;
               check_day integer;
               check_year integer;
               feb_end_day integer;
BEGIN
               check_year := CASE WHEN (string_to_array(check_date,'-'))[1] ~ '[0-9]+' THEN (string_to_array(check_date,'-'))[1] ELSE null END;
               check_month := CASE WHEN (string_to_array(check_date,'-'))[2] ~ '[0-9]+' THEN (string_to_array(check_date,'-'))[2] ELSE null END;
               check_day := CASE WHEN (string_to_array(check_date,'-'))[3] ~ '[0-9]+' THEN (string_to_array(check_date,'-'))[3] ELSE null END;

               IF check_year is null OR check_month is null OR check_day is null THEN
                              RETURN false;
               ELSE
                              CASE check_month
                                             WHEN 1,3,5,7,8,10,12 THEN
                                                            IF check_day > 0 and check_day <=31 THEN
                                                                           RETURN true;
                                                            ELSE
                                                                           RETURN false;
                                                            END IF;
                                             WHEN 4,6,9,11 THEN
                                                            IF check_day > 0 and check_day <=30 THEN
                                                                           RETURN true;
                                                            ELSE
                                                                           RETURN false;
                                                            END IF;
                                             WHEN 2 THEN
                                                            feb_end_day := date_part('day',date((string_to_array(check_date,'-'))[1] || '-03-01') - interval '1 day');
                                                            IF check_day > 0 and check_day <= feb_end_day THEN
                                                                           RETURN true;
                                                            ELSE
                                                                           RETURN false;
                                                            END IF;
                                             ELSE
                                                            RETURN false;
                              END CASE;
               END IF;
END
$$;


ALTER FUNCTION public.is_date(check_date character varying) OWNER TO postgres;

--
-- Name: is_extended_fact(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION is_extended_fact(fact_id_arg integer) RETURNS boolean
    LANGUAGE plpgsql
    AS $$
DECLARE
	is_base_var boolean;
BEGIN
	SELECT n.is_base 
	INTO is_base_var
	FROM namespace n
	JOIN qname q
	  ON n.uri = q.namespace
	JOIN element e
	  ON q.qname_id = e.qname_id
	JOIN fact f
	  ON e.element_id = f.element_id
	WHERE f.fact_id = fact_id_arg;

	IF is_base_var THEN
		SELECT bool_and(nd.is_base and nm.is_base)
		INTO is_base_var
		FROM context_dimension cd
		JOIN fact f
		  ON cd.context_id = f.context_id
		JOIN qname qd
		  ON cd.dimension_qname_id = qd.qname_id
		JOIN namespace nd
		  ON qd.namespace = nd.uri
		JOIN qname qm
		  ON cd.member_qname_id = qm.qname_id
		JOIN namespace nm
		  ON qm.namespace = nm.uri
		WHERE f.fact_id = fact_id_arg
		  AND cd.is_default = false;

		IF coalesce(is_base_var,true) THEN
			RETURN false;
		ELSE
			RETURN true;
		END IF;
	ELSE
		RETURN true;
	END IF;
	
END
$$;


ALTER FUNCTION public.is_extended_fact(fact_id_arg integer) OWNER TO postgres;

--
-- Name: list_dimensional_qualifications(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION list_dimensional_qualifications(context_id_arg integer) RETURNS character varying[]
    LANGUAGE plpgsql
    AS $$
DECLARE
cd_record RECORD;
dimension_list varchar[];
dimension_row  varchar[];
BEGIN

	FOR cd_record IN 
		SELECT qa.namespace as dim_namespace
		,qa.local_name as dim_local_name
		,qm.namespace as mem_namespace
		,qm.local_name as mem_local_name
		FROM context_dimension cd
		JOIN qname qa
		   ON cd.dimension_qname_id = qa.qname_id
		JOIN qname qm
		   ON cd.member_qname_id = qm.qname_id
		WHERE context_id = context_id_arg
		   AND is_default = false
		ORDER BY 2, 1, 4, 3
  
	LOOP
	dimension_row :=  ARRAY[ARRAY['', cd_record.dim_local_name, '', cd_record.mem_local_name]];
	dimension_list := dimension_list || dimension_row;
	END LOOP;
	return dimension_list;
END
$$;


ALTER FUNCTION public.list_dimensional_qualifications(context_id_arg integer) OWNER TO postgres;

--
-- Name: list_dimensional_qualifications_for_fact(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION list_dimensional_qualifications_for_fact(fact_id_arg integer) RETURNS character varying[]
    LANGUAGE plpgsql
    AS $$
DECLARE
context_id_var integer;
cd_record RECORD;
dimension_list varchar[];
dimension_row  varchar[];
BEGIN
	SELECT context_id INTO context_id_var FROM fact WHERE fact_id = fact_id_arg;

	FOR cd_record IN 
		SELECT qa.namespace as dim_namespace
			,qa.local_name as dim_local_name
		,qm.namespace as mem_namespace
		,qm.local_name as mem_local_name
		FROM context_dimension cd
		JOIN qname qa
		   ON cd.dimension_qname_id = qa.qname_id
		JOIN qname qm
		   ON cd.member_qname_id = qm.qname_id
		WHERE context_id = context_id_var
		   AND is_default = false
		ORDER BY 2, 1, 4, 3
	LOOP
	dimension_row :=  ARRAY[ARRAY['', cd_record.dim_local_name, '', cd_record.mem_local_name]];
	dimension_list := dimension_list || dimension_row;
	END LOOP;
	return dimension_list;
END
$$;


ALTER FUNCTION public.list_dimensional_qualifications_for_fact(fact_id_arg integer) OWNER TO postgres;

--
-- Name: make_tsquery(character varying); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION make_tsquery(query character varying) RETURNS tsquery
    LANGUAGE sql
    AS $_$

               -- This regular expression replaces spaces between words
               select to_tsquery(regexp_replace(regexp_replace(regexp_replace(regexp_replace($1, E'\\s+not\\s+',' ! ','gi'), E'\\s+or\\s+',' | ','gi'), E'\\s+and\\s+',' & ','gi'),E'(\\w)(\\s+)(\\w)',E'\\1 & \\3','g'));

$_$;


ALTER FUNCTION public.make_tsquery(query character varying) OWNER TO postgres;

--
-- Name: normalize_space(text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION normalize_space(text) RETURNS text
    LANGUAGE sql IMMUTABLE
    AS $_$
SELECT regexp_replace(
    trim($1),
    E'\\s+',
    ' ',
    'g'
);
$_$;


ALTER FUNCTION public.normalize_space(text) OWNER TO postgres;

--
-- Name: overlap_interval(date, date, date, date); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION overlap_interval(a_start date, a_end date, b_start date, b_end date) RETURNS interval
    LANGUAGE plpgsql
    AS $$
DECLARE

BEGIN
               -- If there is no overlap then
               IF NOT (a_start, a_end) OVERLAPS (b_start, b_end)  THEN
                              RETURN 0;
               END IF;

               RETURN LEAST(a_end, b_end)::timestamp - GREATEST(a_start, b_start)::timestamp;

END
$$;


ALTER FUNCTION public.overlap_interval(a_start date, a_end date, b_start date, b_end date) OWNER TO postgres;

--
-- Name: pgp_key_id(bytea); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION pgp_key_id(bytea) RETURNS text
    LANGUAGE c IMMUTABLE STRICT
    AS '$libdir/pgcrypto', 'pgp_key_id_w';


ALTER FUNCTION public.pgp_key_id(bytea) OWNER TO postgres;

--
-- Name: pgp_pub_decrypt(bytea, bytea); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION pgp_pub_decrypt(bytea, bytea) RETURNS text
    LANGUAGE c IMMUTABLE STRICT
    AS '$libdir/pgcrypto', 'pgp_pub_decrypt_text';


ALTER FUNCTION public.pgp_pub_decrypt(bytea, bytea) OWNER TO postgres;

--
-- Name: pgp_pub_decrypt(bytea, bytea, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION pgp_pub_decrypt(bytea, bytea, text) RETURNS text
    LANGUAGE c IMMUTABLE STRICT
    AS '$libdir/pgcrypto', 'pgp_pub_decrypt_text';


ALTER FUNCTION public.pgp_pub_decrypt(bytea, bytea, text) OWNER TO postgres;

--
-- Name: pgp_pub_decrypt(bytea, bytea, text, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION pgp_pub_decrypt(bytea, bytea, text, text) RETURNS text
    LANGUAGE c IMMUTABLE STRICT
    AS '$libdir/pgcrypto', 'pgp_pub_decrypt_text';


ALTER FUNCTION public.pgp_pub_decrypt(bytea, bytea, text, text) OWNER TO postgres;

--
-- Name: pgp_pub_decrypt_bytea(bytea, bytea); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION pgp_pub_decrypt_bytea(bytea, bytea) RETURNS bytea
    LANGUAGE c IMMUTABLE STRICT
    AS '$libdir/pgcrypto', 'pgp_pub_decrypt_bytea';


ALTER FUNCTION public.pgp_pub_decrypt_bytea(bytea, bytea) OWNER TO postgres;

--
-- Name: pgp_pub_decrypt_bytea(bytea, bytea, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION pgp_pub_decrypt_bytea(bytea, bytea, text) RETURNS bytea
    LANGUAGE c IMMUTABLE STRICT
    AS '$libdir/pgcrypto', 'pgp_pub_decrypt_bytea';


ALTER FUNCTION public.pgp_pub_decrypt_bytea(bytea, bytea, text) OWNER TO postgres;

--
-- Name: pgp_pub_decrypt_bytea(bytea, bytea, text, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION pgp_pub_decrypt_bytea(bytea, bytea, text, text) RETURNS bytea
    LANGUAGE c IMMUTABLE STRICT
    AS '$libdir/pgcrypto', 'pgp_pub_decrypt_bytea';


ALTER FUNCTION public.pgp_pub_decrypt_bytea(bytea, bytea, text, text) OWNER TO postgres;

--
-- Name: pgp_pub_encrypt(text, bytea); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION pgp_pub_encrypt(text, bytea) RETURNS bytea
    LANGUAGE c STRICT
    AS '$libdir/pgcrypto', 'pgp_pub_encrypt_text';


ALTER FUNCTION public.pgp_pub_encrypt(text, bytea) OWNER TO postgres;

--
-- Name: pgp_pub_encrypt(text, bytea, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION pgp_pub_encrypt(text, bytea, text) RETURNS bytea
    LANGUAGE c STRICT
    AS '$libdir/pgcrypto', 'pgp_pub_encrypt_text';


ALTER FUNCTION public.pgp_pub_encrypt(text, bytea, text) OWNER TO postgres;

--
-- Name: pgp_pub_encrypt_bytea(bytea, bytea); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION pgp_pub_encrypt_bytea(bytea, bytea) RETURNS bytea
    LANGUAGE c STRICT
    AS '$libdir/pgcrypto', 'pgp_pub_encrypt_bytea';


ALTER FUNCTION public.pgp_pub_encrypt_bytea(bytea, bytea) OWNER TO postgres;

--
-- Name: pgp_pub_encrypt_bytea(bytea, bytea, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION pgp_pub_encrypt_bytea(bytea, bytea, text) RETURNS bytea
    LANGUAGE c STRICT
    AS '$libdir/pgcrypto', 'pgp_pub_encrypt_bytea';


ALTER FUNCTION public.pgp_pub_encrypt_bytea(bytea, bytea, text) OWNER TO postgres;

--
-- Name: pgp_sym_decrypt(bytea, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION pgp_sym_decrypt(bytea, text) RETURNS text
    LANGUAGE c IMMUTABLE STRICT
    AS '$libdir/pgcrypto', 'pgp_sym_decrypt_text';


ALTER FUNCTION public.pgp_sym_decrypt(bytea, text) OWNER TO postgres;

--
-- Name: pgp_sym_decrypt(bytea, text, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION pgp_sym_decrypt(bytea, text, text) RETURNS text
    LANGUAGE c IMMUTABLE STRICT
    AS '$libdir/pgcrypto', 'pgp_sym_decrypt_text';


ALTER FUNCTION public.pgp_sym_decrypt(bytea, text, text) OWNER TO postgres;

--
-- Name: pgp_sym_decrypt_bytea(bytea, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION pgp_sym_decrypt_bytea(bytea, text) RETURNS bytea
    LANGUAGE c IMMUTABLE STRICT
    AS '$libdir/pgcrypto', 'pgp_sym_decrypt_bytea';


ALTER FUNCTION public.pgp_sym_decrypt_bytea(bytea, text) OWNER TO postgres;

--
-- Name: pgp_sym_decrypt_bytea(bytea, text, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION pgp_sym_decrypt_bytea(bytea, text, text) RETURNS bytea
    LANGUAGE c IMMUTABLE STRICT
    AS '$libdir/pgcrypto', 'pgp_sym_decrypt_bytea';


ALTER FUNCTION public.pgp_sym_decrypt_bytea(bytea, text, text) OWNER TO postgres;

--
-- Name: pgp_sym_encrypt(text, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION pgp_sym_encrypt(text, text) RETURNS bytea
    LANGUAGE c STRICT
    AS '$libdir/pgcrypto', 'pgp_sym_encrypt_text';


ALTER FUNCTION public.pgp_sym_encrypt(text, text) OWNER TO postgres;

--
-- Name: pgp_sym_encrypt(text, text, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION pgp_sym_encrypt(text, text, text) RETURNS bytea
    LANGUAGE c STRICT
    AS '$libdir/pgcrypto', 'pgp_sym_encrypt_text';


ALTER FUNCTION public.pgp_sym_encrypt(text, text, text) OWNER TO postgres;

--
-- Name: pgp_sym_encrypt_bytea(bytea, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION pgp_sym_encrypt_bytea(bytea, text) RETURNS bytea
    LANGUAGE c STRICT
    AS '$libdir/pgcrypto', 'pgp_sym_encrypt_bytea';


ALTER FUNCTION public.pgp_sym_encrypt_bytea(bytea, text) OWNER TO postgres;

--
-- Name: pgp_sym_encrypt_bytea(bytea, text, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION pgp_sym_encrypt_bytea(bytea, text, text) RETURNS bytea
    LANGUAGE c STRICT
    AS '$libdir/pgcrypto', 'pgp_sym_encrypt_bytea';


ALTER FUNCTION public.pgp_sym_encrypt_bytea(bytea, text, text) OWNER TO postgres;

--
-- Name: print_industry_hierarchy(character varying, integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION print_industry_hierarchy(industry_classification_arg character varying, root_arg integer) RETURNS SETOF industry_hierarchy
    LANGUAGE plpgsql
    AS $$
DECLARE
	children_cur	refcursor;
	child_var	RECORD;
	result_var	RECORD;

BEGIN

	IF root_arg IS NULL THEN	
		OPEN children_cur FOR SELECT * 
				      FROM industry 
				      WHERE industry_classification = industry_classification_arg 
				        AND depth = 1 
				      ORDER BY industry_code;
	ELSE
		OPEN children_cur FOR SELECT * 
				      FROM industry 
				      WHERE industry_classification = industry_classification_arg 
				        AND parent_id = root_arg 
				      ORDER BY industry_code;
	END IF;

	FETCH children_cur INTO child_var;

	WHILE FOUND LOOP

		SELECT industry_classification_arg
			,child_var.industry_id
			,child_var.depth
			,child_var.industry_code
			,(repeat('  ',child_var.depth - 1) || child_var.industry_code::varchar)::varchar
			,child_var.industry_description
			,child_var.parent_id
		INTO result_var;

		RETURN NEXT result_var;
			   
		RETURN QUERY SELECT * FROM print_industry_hierarchy(industry_classification_arg, child_var.industry_id);	
		
		FETCH children_cur INTO child_var; 
		  
	END LOOP;

	CLOSE children_cur;

	RETURN;
END
$$;


ALTER FUNCTION public.print_industry_hierarchy(industry_classification_arg character varying, root_arg integer) OWNER TO postgres;

--
-- Name: set_creation_software_short(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION set_creation_software_short() RETURNS integer
    LANGUAGE plpgsql
    AS $$

DECLARE
  m_total INTEGER;
  m_updated INTEGER;

BEGIN
    m_total := 0;

    UPDATE accession
    SET creation_software_short = 'Rivet'
    WHERE creation_software_short IS NULL
      AND creation_software ilike '%Rivet%';

    GET DIAGNOSTICS m_updated = ROW_COUNT;
    SELECT INTO m_total m_total + m_updated;

    UPDATE accession
    SET creation_software_short = 'FilePoint'
    WHERE creation_software_short IS NULL
      AND creation_software ilike '%filepoint%';

    GET DIAGNOSTICS m_updated = ROW_COUNT;
    SELECT INTO m_total m_total + m_updated;

    UPDATE accession
    SET creation_software_short = 'EDGARizerX'
    WHERE creation_software_short IS NULL
      AND creation_software ilike '%EDGARizerX%';

    GET DIAGNOSTICS m_updated = ROW_COUNT;
    SELECT INTO m_total m_total + m_updated;

    UPDATE accession
    SET creation_software_short = 'EDGAR Online'
    WHERE creation_software_short IS NULL
      AND creation_software ilike '%EDGAR Online%';

    GET DIAGNOSTICS m_updated = ROW_COUNT;
    SELECT INTO m_total m_total + m_updated;

    UPDATE accession
    SET creation_software_short = 'Bowne'
    WHERE creation_software_short IS NULL
      AND creation_software ilike '%Bowne%';

    GET DIAGNOSTICS m_updated = ROW_COUNT;
    SELECT INTO m_total m_total + m_updated;

    UPDATE accession
    SET creation_software_short = 'Clarity'
    WHERE creation_software_short IS NULL
      AND creation_software ilike '%Clarity%';

    GET DIAGNOSTICS m_updated = ROW_COUNT;
    SELECT INTO m_total m_total + m_updated;

    UPDATE accession
    SET creation_software_short = 'Business Wire'
    WHERE creation_software_short IS NULL
      AND creation_software ilike '%Business Wire%';

    GET DIAGNOSTICS m_updated = ROW_COUNT;
    SELECT INTO m_total m_total + m_updated;

    UPDATE accession
    SET creation_software_short = 'WebFilings'
    WHERE creation_software_short IS NULL
      AND creation_software ilike '%WebFilings%';

    GET DIAGNOSTICS m_updated = ROW_COUNT;
    SELECT INTO m_total m_total + m_updated;

    UPDATE accession
    SET creation_software_short = 'CompSci'
    WHERE creation_software_short IS NULL
      AND creation_software ilike '%CompSci%';

    GET DIAGNOSTICS m_updated = ROW_COUNT;
    SELECT INTO m_total m_total + m_updated;

    UPDATE accession
    SET creation_software_short = 'Novaworks Software'
    WHERE creation_software_short IS NULL
      AND creation_software ilike '%GoFiler%';

    GET DIAGNOSTICS m_updated = ROW_COUNT;
    SELECT INTO m_total m_total + m_updated;

    UPDATE accession
    SET creation_software_short = 'UBMatrix'
    WHERE creation_software_short IS NULL
      AND creation_software ilike '%UBMatrix%';

    GET DIAGNOSTICS m_updated = ROW_COUNT;
    SELECT INTO m_total m_total + m_updated;

    UPDATE accession
    SET creation_software_short = 'Ez-XBRL'
    WHERE creation_software_short IS NULL
      AND creation_software ilike '%Ez-XBRL%';

    GET DIAGNOSTICS m_updated = ROW_COUNT;
    SELECT INTO m_total m_total + m_updated;

    UPDATE accession
    SET creation_software_short = 'Ez-XBRL'
    WHERE creation_software_short IS NULL
      AND creation_software ilike '%EzXBRL%';

    GET DIAGNOSTICS m_updated = ROW_COUNT;
    SELECT INTO m_total m_total + m_updated;

    UPDATE accession
    SET creation_software_short = 'Trintech'
    WHERE creation_software_short IS NULL
      AND creation_software ilike '%Trintech%';

    GET DIAGNOSTICS m_updated = ROW_COUNT;
    SELECT INTO m_total m_total + m_updated;

    UPDATE accession
    SET creation_software_short = 'Oracle'
    WHERE creation_software_short IS NULL
      AND creation_software ilike '%Oracle%';

    GET DIAGNOSTICS m_updated = ROW_COUNT;
    SELECT INTO m_total m_total + m_updated;

    UPDATE accession
    SET creation_software_short = 'Snappy Reports'
    WHERE creation_software_short IS NULL
      AND creation_software ilike '%Snappy Reports%';

    GET DIAGNOSTICS m_updated = ROW_COUNT;
    SELECT INTO m_total m_total + m_updated;

    UPDATE accession
    SET creation_software_short = 'NeoClarus'
    WHERE creation_software_short IS NULL
      AND creation_software ilike '%NeoClarus%';

    GET DIAGNOSTICS m_updated = ROW_COUNT;
    SELECT INTO m_total m_total + m_updated;

    UPDATE accession
    SET creation_software_short = 'Advanced Computer Innovations'
    WHERE creation_software_short IS NULL
      AND creation_software ilike '%Advanced Computer Innovations%';

    UPDATE accession
    SET creation_software_short = 'RR Donnelley'
    WHERE creation_software_short IS NULL
      AND creation_software ilike '%RR Donnelley%';

    UPDATE accession
    SET creation_software_short = 'P3XBRL'
    WHERE creation_software_short IS NULL
      AND creation_software ilike '%P3XBRL%';

    UPDATE accession
    SET creation_software_short = 'GoXBRL'
    WHERE creation_software_short IS NULL
      AND creation_software ilike '%GoXBRL%';

    UPDATE accession
    SET creation_software_short = 'QXi'
    WHERE creation_software_short IS NULL
      AND creation_software ilike '%QXi%';

    UPDATE accession
    SET creation_software_short = 'WLB Universal Editor'
    WHERE creation_software_short IS NULL
      AND creation_software ilike '%WLB Universal Editor%';

    GET DIAGNOSTICS m_updated = ROW_COUNT;
    SELECT INTO m_total m_total + m_updated;

    UPDATE accession
    SET creation_software_short = 'Compliance Xpressware'
    WHERE creation_software_short IS NULL
      AND creation_software ilike '%Compliance Xpressware%';

    GET DIAGNOSTICS m_updated = ROW_COUNT;
    SELECT INTO m_total m_total + m_updated;

    UPDATE accession
    SET creation_software_short = 'Fujitsu'
    WHERE creation_software_short IS NULL
      AND TRIM(creation_software) ilike '%XWand B%';

    UPDATE accession
    SET creation_software_short = 'Fujitsu'
    WHERE creation_software_short IS NULL
      AND TRIM(creation_software) ilike 'Generated by Fujitsu XWand%';

    GET DIAGNOSTICS m_updated = ROW_COUNT;
    SELECT INTO m_total m_total + m_updated;

    -- Hack for junk
    UPDATE accession
    SET creation_software_short = ''
    WHERE creation_software_short IS NULL
      AND creation_software LIKE '%<%';

    GET DIAGNOSTICS m_updated = ROW_COUNT;
    SELECT INTO m_total m_total + m_updated;

    UPDATE accession
    SET creation_software_short = ''
    WHERE creation_software_short IS NULL
      AND TRIM(creation_software) = '';

    GET DIAGNOSTICS m_updated = ROW_COUNT;
    SELECT INTO m_total m_total + m_updated;

    UPDATE accession
    SET creation_software_short = ''
    WHERE creation_software_short IS NULL
      AND creation_software IS NULL;

    GET DIAGNOSTICS m_updated = ROW_COUNT;
    SELECT INTO m_total m_total + m_updated;

    RAISE NOTICE 'Updated creation_software_short for % rows', m_total;

    return m_total;

END $$;


ALTER FUNCTION public.set_creation_software_short() OWNER TO postgres;

--
-- Name: set_document_type(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION set_document_type() RETURNS integer
    LANGUAGE plpgsql
    AS $$

DECLARE
  m_updated INTEGER;

BEGIN

    UPDATE accession
    SET document_type = fact.fact_value
    FROM fact
    JOIN element ON element.element_id = fact.element_id
    JOIN qname ON qname.qname_id = element.qname_id
    WHERE fact.accession_id = accession.accession_id
      AND qname.namespace LIKE '%/dei/%'
      AND qname.local_name = 'DocumentType'
      AND accession.document_type IS NULL;

    GET DIAGNOSTICS m_updated = ROW_COUNT;

    RAISE NOTICE 'Updated document_type for % rows', m_updated;

    RETURN m_updated;

END $$;


ALTER FUNCTION public.set_document_type() OWNER TO postgres;

--
-- Name: set_extension_count(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION set_extension_count() RETURNS integer
    LANGUAGE plpgsql
    AS $$

DECLARE
  m_updated INTEGER;

BEGIN

    UPDATE accession updateme
    SET percent_extended = fromhere.percent_extended
    FROM (SELECT accession_id, extension_count, total_count, ((extension_count * 100) / total_count) as percent_extended
            FROM (SELECT uaq1.accession_id
                 ,SUM(CASE WHEN qname.namespace NOT LIKE 'http://xbrl.us/%' AND
                                qname.namespace NOT LIKE 'http://taxonomies.xbrl.us/%' AND
                                qname.namespace NOT LIKE 'http://xbrl.fasb.org/%' AND
                                -- http://fasb.org isn't right, but FASB has been very unclear
                                qname.namespace NOT LIKE 'http://fasb.org/%' AND
                                qname.namespace NOT LIKE 'http://xbrl.sec.gov/%' THEN 1
                           ELSE 0
                           END) AS extension_count
                          ,COUNT(*) AS total_count
             FROM (SELECT DISTINCT accession.accession_id, qname.qname_id
                   FROM accession
                   JOIN fact ON fact.accession_id = accession.accession_id
                   JOIN element ON element.element_id = fact.element_id
                   JOIN qname ON qname.qname_id = element.qname_id
                   WHERE accession.percent_extended IS NULL

                     UNION

                   SELECT DISTINCT accession.accession_id, qname.qname_id
                     FROM accession
                     JOIN context on context.accession_id = accession.accession_id
                     JOIN context_dimension ON context_dimension.context_id = context.context_id
                     JOIN qname ON qname.qname_id = context_dimension.dimension_qname_id
                     WHERE accession.percent_extended IS NULL

                       UNION

                   SELECT DISTINCT accession.accession_id, qname.qname_id
                     FROM accession
                     JOIN context on context.accession_id = accession.accession_id
                     JOIN context_dimension ON context_dimension.context_id = context.context_id
                     JOIN qname ON qname.qname_id = context_dimension.member_qname_id
                     WHERE accession.percent_extended IS NULL) uaq1
             JOIN qname ON qname.qname_id = uaq1.qname_id
           GROUP BY uaq1.accession_id) pext) fromhere
    WHERE extension_count IS NOT NULL
    AND fromhere.accession_id = updateme.accession_id;

    GET DIAGNOSTICS m_updated = ROW_COUNT;

    RAISE NOTICE 'Updated percent_extended for % rows', m_updated;

    RETURN m_updated;

END $$;


ALTER FUNCTION public.set_extension_count() OWNER TO postgres;

--
-- Name: taxonomy_type(character varying); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION taxonomy_type(namespace_uri_arg character varying) RETURNS character varying
    LANGUAGE plpgsql
    AS $$
DECLARE
               taxonomy_version_name character varying;
BEGIN
               SELECT t.name || '(' || tv.version || ')'
               INTO taxonomy_version_name
               FROM taxonomy t
               JOIN taxonomy_version tv
                 ON t.taxonomy_id = tv.taxonomy_id
               JOIN namespace n
                 ON tv.taxonomy_version_id = n.taxonomy_version_id
               WHERE n.uri = namespace_uri_arg;

               IF taxonomy_version_name IS NULL THEN
                              RETURN 'extension';
               ELSE
                              RETURN taxonomy_version_name;
               END IF;
END
$$;


ALTER FUNCTION public.taxonomy_type(namespace_uri_arg character varying) OWNER TO postgres;

--
-- Name: ticker(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION ticker(integer) RETURNS character varying
    LANGUAGE sql
    AS $_$
/* This function determines the ticker (trading symbol) for an entity based on the file name of the latest accession.
   It takes the entity_id as the input
*/
               SELECT MAX(SUBSTRING(document_uri, E'([^/]*)-\\d\\d\\d\\d\\d\\d\\d\\d\\.x..$'))
               FROM   accession_document_association ada
                 JOIN document d
                   ON ada.document_id = d.document_id
               WHERE document_uri ~* E'http://www.sec.gov/.*/[^_]*\\.xml$'
               AND   ada.accession_id = (
                              SELECT max(accession_id)
                              FROM accession
                              WHERE entity_id = $1
                              AND   filing_date = (
                                             SELECT MAX(filing_date)
                                             FROM accession
                                             WHERE entity_id = $1)
               )
$_$;


ALTER FUNCTION public.ticker(integer) OWNER TO postgres;

--
-- Name: uom(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION uom(unit_id_arg integer) RETURNS character varying
    LANGUAGE plpgsql
    AS $$
DECLARE
               uom_cursor NO SCROLL CURSOR (unit_id_key integer)  FOR
                              SELECT um.*, qum.*
                              FROM   unit_measure um
                                JOIN qname qum
                                  ON qum.qname_id = um.qname_id
                              WHERE unit_id = unit_id_key
                              ORDER BY location_id DESC;

               compound_unit boolean := false;
               uom_numerator character varying := '';
               uom_divisor character varying :='';
               clean_name character varying;
               uom_result character varying := '';

BEGIN
               IF NOT unit_id_arg is null THEN
                              FOR uom_row IN uom_cursor (unit_id_arg) LOOP
                                             clean_name := trim(regexp_replace(coalesce(uom_row.local_name,''),E'[\f\n\r\t\v]','','g'));
                                             IF uom_row.location_id in (2,3) THEN compound_unit := true; END IF;
                                             CASE
                                                            WHEN uom_row.location_id = 3 THEN
                                                                           IF uom_divisor != '' THEN
                                                                                          uom_divisor := uom_divisor || ' * ';
                                                                           END IF;
                                                                           uom_divisor := uom_divisor || clean_name;
                                                            ELSE
                                                                           IF (NOT compound_unit) OR (compound_unit AND uom_row.location_id != 1) THEN
                                                                                          IF uom_numerator != '' THEN
                                                                                                         uom_numerator := uom_numerator || ' * ';
                                                                                          END IF;
                                                                                          uom_numerator := uom_numerator || clean_name;
                                                                           END IF;
                                             END CASE;
                              END LOOP;

                              uom_result := trim(uom_numerator);
                              IF uom_divisor != '' THEN
                                             uom_result := uom_result || '/' || trim(uom_divisor);
                              END IF;

                              return uom_result;
               ELSE
                              return null;
               END IF;
END
$$;


ALTER FUNCTION public.uom(unit_id_arg integer) OWNER TO postgres;

--
-- Name: update_accession_element_by_accession(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION update_accession_element_by_accession(accession_id_arg integer) RETURNS void
    LANGUAGE plpgsql
    AS $_$
DECLARE
	rand character varying;
	accession_element_list character varying;
	accession_element_primary character varying;
	accession_element_dimension character varying;
	accession_element_member character varying;
BEGIN

	-- generate a random number to use in the table names
	SELECT (random() * 100000000)::integer::varchar INTO rand;
	accession_element_list := 'list_' || rand;
	accession_element_primary := 'primary_' || rand;
	accession_element_dimension := 'dimension_' || rand;
	accession_element_member := 'member_' || rand;

	-- delete any accession_element records for the accession
	DELETE FROM accession_element
	WHERE accession_id = accession_id_arg;

	EXECUTE '
	CREATE TEMP TABLE ' || accession_element_list || ' AS
	WITH toandfrom as (
		SELECT from_element_id as element_id, accession_id, is_base(q.namespace) as is_base
		FROM relationship r
		JOIN network
		  USING (network_id)
		JOIN element e
		  ON r.from_element_id = e.element_id
		JOIN qname q
		  USING (qname_id)
		WHERE accession_id = $1

		UNION

		SELECT to_element_id, accession_id, is_base(q.namespace)
		FROM relationship r
		JOIN network
		  USING (network_id)
		JOIN element e
		  ON r.to_element_id = e.element_id
		JOIN qname q
		  USING (qname_id)
		WHERE accession_id = $1
	)


	SELECT DISTINCT element_id, accession_id, is_base
	FROM toandfrom
	WHERE element_id is not null'
	USING accession_id_arg;

	-- primary count
	EXECUTE '
	CREATE TEMP TABLE ' || accession_element_primary || ' AS
	SELECT ael.element_id, count(*)
	FROM ' || accession_element_list || ' ael
	JOIN fact f
	  ON ael.element_id = f.element_id
	 AND f.accession_id = $1
	GROUP BY 1'
	USING accession_id_arg;
	
	-- dimension count
	EXECUTE '
	CREATE TEMP TABLE ' || accession_element_dimension || ' AS
	SELECT ael.element_id, count(*)
	FROM ' || accession_element_list || ' ael
	JOIN element e
	  ON ael.element_id = e.element_id
	JOIN context_dimension cd
	  ON e.qname_id = cd.dimension_qname_id
	JOIN context c
	  ON cd.context_id = c.context_id
	JOIN fact f
	  ON c.context_id = f.context_id
	WHERE c.accession_id = $1
	  AND f.accession_id = $1
	  AND cd.is_default = false
	GROUP BY 1'
	USING accession_id_arg;

	-- member count
	EXECUTE '
	CREATE TEMP TABLE ' || accession_element_member || ' AS
	SELECT ael.element_id, count(*)
	FROM ' || accession_element_list || ' ael
	JOIN element e
	  ON ael.element_id = e.element_id
	JOIN context_dimension cd
	  ON e.qname_id = cd.member_qname_id
	JOIN context c
	  ON cd.context_id = c.context_id
	JOIN fact f
	  ON c.context_id = f.context_id
	WHERE c.accession_id = $1
	  AND f.accession_id = $1
	  AND cd.is_default = false
	GROUP BY 1'	 
	USING accession_id_arg;

	-- add the accession_element records.
	EXECUTE '
	INSERT INTO accession_element (element_id, accession_id, is_base, primary_count, dimension_count, member_count)
	SELECT ael.element_id
	      ,ael.accession_id
	      ,ael.is_base
	      ,aep.count
	      ,aed.count
	      ,aem.count
	FROM ' || accession_element_list || ' ael
	LEFT JOIN ' || accession_element_primary || ' aep
	  ON ael.element_id = aep.element_id
	LEFT JOIN ' || accession_element_dimension || ' aed
	  ON ael.element_id = aed.element_id
	LEFT JOIN ' || accession_element_member || ' aem
	  ON ael.element_id = aem.element_id';

	EXECUTE 'DROP TABLE ' || accession_element_list;
	EXECUTE 'DROP TABLE ' || accession_element_primary;
	EXECUTE 'DROP TABLE ' || accession_element_dimension;
	EXECUTE 'DROP TABLE ' || accession_element_member;

END
$_$;


ALTER FUNCTION public.update_accession_element_by_accession(accession_id_arg integer) OWNER TO postgres;

--
-- Name: update_all_period_index(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION update_all_period_index() RETURNS integer
    LANGUAGE plpgsql
    AS $$

DECLARE
	m_updated INTEGER;
BEGIN

	LOCK TABLE accession IN EXCLUSIVE MODE;


	UPDATE accession ua
	SET period_index = rn
	   ,is_most_current = CASE WHEN rn = 1 THEN true ELSE false END
	FROM (SELECT row_number() over(w) AS rn, entity_id, accepted_timestamp, period_end, accession_id, restatement_index
	      FROM (SELECT entity_id, accepted_timestamp, accession.accession_id, period_end, restatement_index
		    FROM accession
		    JOIN (SELECT f.accession_id, max(c.period_end) period_end
			  FROM fact f
			  JOIN element e
			    ON f.element_id = e.element_id
			  JOIN qname q
			    ON e.qname_id = q.qname_id
			  JOIN context c
			    ON f.context_id = c.context_id
			  JOIN accession a
			    ON f.accession_id = a.accession_id
			  WHERE q.namespace like '%/dei/%'
			    AND q.local_name = 'DocumentPeriodEndDate'
			  GROUP BY f.accession_id) accession_period_end
		      ON accession.accession_id = accession_period_end.accession_id) accession_list

	WINDOW w AS (partition BY entity_id ORDER BY period_end DESC, restatement_index ASC)) AS x
	WHERE ua.accession_id = x.accession_id;

	GET DIAGNOSTICS m_updated = ROW_COUNT;
	RAISE NOTICE 'Updated % accessions', m_updated;
	
	UPDATE entity e 
		SET entity_name = a.entity_name 
		FROM (SELECT entity_id, entity_name FROM accession WHERE period_index = 1) as a
		WHERE e.entity_id = a.entity_id;
		
	RETURN m_updated;

END $$;


ALTER FUNCTION public.update_all_period_index() OWNER TO postgres;

--
-- Name: update_all_restatement_index(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION update_all_restatement_index() RETURNS integer
    LANGUAGE plpgsql
    AS $$

DECLARE
	m_updated INTEGER;

BEGIN
	LOCK TABLE accession IN EXCLUSIVE MODE;


	UPDATE accession ua  
	SET restatement_index = rn
	FROM (SELECT row_number() over(w) AS rn, entity_id, accepted_timestamp, period_end, accession_id  
	      FROM (SELECT entity_id, accepted_timestamp, accession.accession_id, period_end  
		    FROM accession  
		    JOIN (SELECT f.accession_id, max(c.period_end) period_end
			  FROM fact f
			  JOIN element e
			    ON f.element_id = e.element_id
			  JOIN qname q
			    ON e.qname_id = q.qname_id
			  JOIN context c
			    ON f.context_id = c.context_id
			  JOIN accession a
			    ON f.accession_id = a.accession_id
			  WHERE q.namespace like '%/dei/%'  
			    AND q.local_name = 'DocumentPeriodEndDate'
			  GROUP BY f.accession_id) accession_period_end
		      ON accession.accession_id = accession_period_end.accession_id) accession_list  

	WINDOW w AS (partition BY entity_id, period_end ORDER BY accepted_timestamp DESC)) AS x  
	WHERE ua.accession_id = x.accession_id
	  AND coalesce(restatement_index,0) <> rn;

	GET DIAGNOSTICS m_updated = ROW_COUNT;
	RAISE NOTICE 'Updated % accessions', m_updated;

	RETURN m_updated;

END $$;


ALTER FUNCTION public.update_all_restatement_index() OWNER TO postgres;

--
-- Name: update_context_aug_by_accession(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION update_context_aug_by_accession(accession_id_arg integer) RETURNS void
    LANGUAGE plpgsql
    AS $$

BEGIN

               -- update existing context_aug records
               /*

               UPDATE context_aug ca

               SET fiscal_year = fiscal_year(c.*)::integer,

                   fiscal_period = fiscal_period(c.*),

                   calendar_period = (calendar_period_full(c.*)).calendar_period,

                   calendar_year = (calendar_period_full(c.*)).calendar_year,

                   calendar_start_offset = (calendar_period_full(c.*)).calendar_start_offset,

                   calendar_end_offset = (calendar_period_full(c.*)).calendar_end_offset,

                   calendar_period_size_diff_percentage = (calendar_period_full(c.*)).calendar_period_size_diff_percentage,

                   context_hash = hash_context(c.context_id),

                   dimension_hash = hash_dimensional_qualifications(c.context_id)

               FROM context c

               WHERE c.context_id = ca.context_id

                 AND c.accession_id = accession_id_arg;

		*/

	       -- delete existing context_aug records
	       DELETE FROM context_aug ca
	       WHERE context_id IN (
		SELECT context_id FROM context c WHERE c.accession_id = accession_id_arg);
		

               -- insert missing context_aug records

               INSERT INTO context_aug

                              ( context_id

                              ,fiscal_year

                              ,fiscal_period

                              ,calendar_year

                              ,calendar_period

                              ,calendar_start_offset

                              ,calendar_end_offset

                              ,calendar_period_size_diff_percentage

                              ,context_hash)

                              --,dimension_hash)

               SELECT c.context_id

                              ,fiscal_year(c.*)::integer

                              ,fiscal_period(c.*)

                              ,(calendar_period_full(c.*)).calendar_year

                              ,(calendar_period_full(c.*)).calendar_period

                              ,(calendar_period_full(c.*)).calendar_start_offset

                              ,(calendar_period_full(c.*)).calendar_end_offset

                              ,(calendar_period_full(c.*)).calendar_period_size_diff_percentage

                              ,hash_context(c.*)

                              --,hash_dimensional_qualifications(c.*)

               FROM context c

               WHERE c.accession_id = accession_id_arg

                 AND NOT EXISTS (SELECT 1

                                               FROM context_aug ca

                                               WHERE c.context_id = ca.context_id);



END

$$;


ALTER FUNCTION public.update_context_aug_by_accession(accession_id_arg integer) OWNER TO postgres;

--
-- Name: seq_accession; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE seq_accession
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.seq_accession OWNER TO postgres;

--
-- Name: accession; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE accession (
    accession_id integer DEFAULT nextval('seq_accession'::regclass) NOT NULL,
    accepted_timestamp timestamp without time zone DEFAULT now() NOT NULL,
    is_most_current boolean DEFAULT false NOT NULL,
    filing_date date NOT NULL,
    entity_id integer NOT NULL,
    entity_name character varying,
    creation_software text,
    creation_software_short character varying(128),
    standard_industrial_classification integer DEFAULT (-1) NOT NULL,
    state_of_incorporation character varying(30),
    internal_revenue_service_number integer DEFAULT (-1) NOT NULL,
    business_address character varying(1024),
    business_phone character varying(30),
    sec_html_url text,
    entry_url text,
    filing_accession_number character varying(30) NOT NULL,
    zip_url text,
    document_type character varying(20),
    percent_extended integer,
    restatement_index integer,
    period_index integer,
    is_complete boolean DEFAULT false
);


ALTER TABLE public.accession OWNER TO postgres;

--
-- Name: update_entity_name_history(accession); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION update_entity_name_history(accession_arg accession) RETURNS void
    LANGUAGE plpgsql
    AS $$

DECLARE

        last_name_var character varying;
        accession_row accession;

BEGIN

	-- delete all history records that come from accessions after the current accession. 
	-- This can happen if the accessions are not processed in accepted timestamp order.
	DELETE FROM entity_name_history
	WHERE accession_id IN
		(SELECT accession_id
		 FROM accession
		 WHERE entity_id = accession_arg.entity_id
		   AND accepted_timestamp >= accession_arg.accepted_timestamp);

        -- iterate through all accessions after and including the current accession
        FOR accession_row IN SELECT * 
			     FROM accession 
			     WHERE entity_id = accession_arg.entity_id
			       AND accepted_timestamp >= accession_arg.accepted_timestamp
			     ORDER BY accepted_timestamp LOOP 
		-- get the latest entity_name
		SELECT enh.entity_name
		INTO last_name_var
		FROM entity_name_history enh
		JOIN accession a
		  ON enh.accession_id = a.accession_id
		WHERE enh.entity_id = accession_row.entity_id
		ORDER BY a.accepted_timestamp DESC
		LIMIT 1;

		IF (last_name_var IS NULL OR last_name_var <> trim(both accession_row.entity_name)) THEN
			INSERT INTO entity_name_history (entity_id, accession_id, entity_name)
			VALUES (accession_row.entity_id, accession_row.accession_id, trim(both accession_row.entity_name));
		END IF;
		
	END LOOP;
	


				

END;

$$;


ALTER FUNCTION public.update_entity_name_history(accession_arg accession) OWNER TO postgres;

--
-- Name: update_entity_name_history(integer, character varying, integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION update_entity_name_history(entity_id_var integer, new_entity_name_var character varying, accession_id_var integer) RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
        entity_name_var character varying;
BEGIN
        SELECT enh.entity_name
        INTO entity_name_var
        FROM entity_name_history enh
        JOIN accession a
          ON a.accession_id = enh.accession_id
        WHERE enh.entity_id = entity_id_var
        ORDER BY a.filing_date DESC, accepted_timestamp DESC
        LIMIT 1;

        IF (entity_name_var IS NULL OR entity_name_var <> new_entity_name_var) THEN
                INSERT INTO entity_name_history (entity_id, accession_id, entity_name)
                VALUES (entity_id_var, accession_id_var, new_entity_name_var);
        END IF;
END;
$$;


ALTER FUNCTION public.update_entity_name_history(entity_id_var integer, new_entity_name_var character varying, accession_id_var integer) OWNER TO postgres;

--
-- Name: update_fact_aug_by_accession(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION update_fact_aug_by_accession(accession_id_arg integer) RETURNS void
    LANGUAGE plpgsql
    AS $$

DECLARE

               fact_list_row RECORD;



BEGIN

               -- create temp table with the facts that need to be added

               CREATE TEMP TABLE fact_list AS

                              SELECT f.fact_id, hash_fact_string(f.fact_id) as hash_string, unit_id

                              FROM fact f

                              WHERE f.accession_id = accession_id_arg;



               -- delete rows in the fact_aug table that will be replaced.
               

               DELETE FROM fact_aug

               WHERE fact_id IN (SELECT fact_id FROM fact_list);



               -- add the new facts to the fact_aug table

               INSERT INTO fact_aug (fact_id, fact_hash, calendar_hash, uom)

               SELECT fact_id, hash_fact(hash_string), hash_fact(fact_hash_2_calendar(hash_string)), uom(unit_id)

               FROM fact_list;



               -- recalc all the facts with the new hashs



               FOR fact_list_row IN SELECT DISTINCT hash_fact(hash_string) FROM fact_list LOOP

                              PERFORM calc_fact_aug(fact_list_row.hash_fact);

               END LOOP;



               FOR fact_list_row IN SELECT DISTINCT hash_fact(fact_hash_2_calendar(hash_string)) AS calendar_hash FROM fact_list LOOP

                              PERFORM calc_calendar_ultimus(fact_list_row.calendar_hash);

               END LOOP;



               -- drop the fact_list table

               DROP TABLE fact_list;



END

$$;


ALTER FUNCTION public.update_fact_aug_by_accession(accession_id_arg integer) OWNER TO postgres;

--
-- Name: update_fact_by_accession(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION update_fact_by_accession(accession_id_arg integer) RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN

	UPDATE FACT f
	SET ultimus_index = fa.ultimus_index
		,calendar_ultimus_index = fa.calendar_ultimus_index
		,uom = fa.uom
		,fiscal_year = ca.fiscal_year
		,fiscal_period = ca.fiscal_period
		,calendar_year = ca.calendar_year
		,calendar_period = ca.calendar_period
	FROM fact_aug fa
	    ,context_aug ca
	WHERE f.fact_id = fa.fact_id
	  AND f.context_id = ca.context_id
	  AND f.accession_id = accession_id_arg;
	  
END
$$;


ALTER FUNCTION public.update_fact_by_accession(accession_id_arg integer) OWNER TO postgres;

--
-- Name: update_namespace_by_accession(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION update_namespace_by_accession(accession_id_arg integer) RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
	taxonomy_version_id_var integer;
BEGIN
	SELECT base_taxonomy_version(accession_id_arg) INTO taxonomy_version_id_var;

	INSERT INTO namespace (uri, is_base, taxonomy_version_id, "name")
	SELECT DISTINCT q.namespace, false, taxonomy_version_id_var, 'extension'
	FROM qname q
	JOIN element e
	 USING (qname_id)
	JOIN accession_document_association ada
	 USING (document_id)
	WHERE ada.accession_id = accession_id_arg
	  AND NOT EXISTS
		(SELECT 1
		FROM namespace n1
		WHERE n1.uri = q.namespace);
END
$$;


ALTER FUNCTION public.update_namespace_by_accession(accession_id_arg integer) OWNER TO postgres;

--
-- Name: update_specifies_dimensions(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION update_specifies_dimensions(context_id_arg integer) RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE 
	specifies_dimensions_var	BOOLEAN;
BEGIN
	SELECT count(*) != 0
	INTO specifies_dimensions_var
	FROM context_dimension
	WHERE context_id = context_id_arg
	  AND NOT is_default;

	UPDATE context
	SET specifies_dimensions = specifies_dimensions_var
	WHERE context_id = context_id_arg;
END
$$;


ALTER FUNCTION public.update_specifies_dimensions(context_id_arg integer) OWNER TO postgres;

--
-- Name: update_specifies_dimensions_by_accession(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION update_specifies_dimensions_by_accession(accession_id_arg integer) RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
        context_id_var  int;
BEGIN
        FOR context_id_var
        IN      SELECT context_id
                FROM context
                WHERE accession_id = accession_id_arg
        LOOP
                PERFORM update_specifies_dimensions(context_id_var);
        END LOOP;

END
$$;


ALTER FUNCTION public.update_specifies_dimensions_by_accession(accession_id_arg integer) OWNER TO postgres;

--
-- Name: year_to_char(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION year_to_char(year_arg integer) RETURNS character varying
    LANGUAGE plpgsql
    AS $$
BEGIN
               IF char_length(year_arg::varchar) < 4 THEN
                              RETURN to_char(year_arg, '0000');
               ELSE
                              RETURN year_arg::varchar;
               END IF;
END
$$;


ALTER FUNCTION public.year_to_char(year_arg integer) OWNER TO postgres;

--
-- Name: year_to_char(numeric); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION year_to_char(year_arg numeric) RETURNS character varying
    LANGUAGE plpgsql
    AS $$
BEGIN
               IF char_length(year_arg::varchar) < 4 THEN
                              RETURN to_char(year_arg, '0000');
               ELSE
                              RETURN year_arg::varchar;
               END IF;
END
$$;


ALTER FUNCTION public.year_to_char(year_arg numeric) OWNER TO postgres;

--
-- Name: year_to_char(double precision); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION year_to_char(year_arg double precision) RETURNS character varying
    LANGUAGE plpgsql
    AS $$
BEGIN
               IF char_length(year_arg::varchar) < 4 THEN
                              RETURN to_char(year_arg, '0000');
               ELSE
                              RETURN year_arg::varchar;
               END IF;
END
$$;


ALTER FUNCTION public.year_to_char(year_arg double precision) OWNER TO postgres;

--
-- Name: seq_accession_document_association; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE seq_accession_document_association
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.seq_accession_document_association OWNER TO postgres;

--
-- Name: accession_document_association; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE accession_document_association (
    accession_document_association_id integer DEFAULT nextval('seq_accession_document_association'::regclass) NOT NULL,
    accession_id integer NOT NULL,
    document_id integer NOT NULL
);


ALTER TABLE public.accession_document_association OWNER TO postgres;

--
-- Name: accession_element; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE accession_element (
    accession_element_id integer NOT NULL,
    accession_id integer NOT NULL,
    element_id integer NOT NULL,
    is_base boolean NOT NULL,
    primary_count integer,
    dimension_count integer,
    member_count integer
);


ALTER TABLE public.accession_element OWNER TO postgres;

--
-- Name: accession_element_accession_element_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE accession_element_accession_element_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.accession_element_accession_element_id_seq OWNER TO postgres;

--
-- Name: accession_element_accession_element_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE accession_element_accession_element_id_seq OWNED BY accession_element.accession_element_id;


--
-- Name: accession_industry_div; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW accession_industry_div AS
    SELECT accession.accession_id, accession.filing_date, accession.entity_id, accession.creation_software, accession.standard_industrial_classification, accession.state_of_incorporation, accession.internal_revenue_service_number, accession.business_address, accession.business_phone, accession.sec_html_url, accession.entry_url, accession.filing_accession_number, foo2.sic_l1, foo2.division_no FROM accession, (SELECT accession.standard_industrial_classification, accession.accession_id, foo.sic_l1, CASE WHEN ((foo.sic_l1 < (10)::numeric) AND (foo.sic_l1 >= (1)::numeric)) THEN '1'::text WHEN ((foo.sic_l1 < (15)::numeric) AND (foo.sic_l1 >= (10)::numeric)) THEN '2'::text WHEN ((foo.sic_l1 < (18)::numeric) AND (foo.sic_l1 >= (15)::numeric)) THEN '3'::text WHEN ((foo.sic_l1 < (22)::numeric) AND (foo.sic_l1 >= (20)::numeric)) THEN '4'::text WHEN ((foo.sic_l1 < (40)::numeric) AND (foo.sic_l1 >= (22)::numeric)) THEN '5'::text WHEN ((foo.sic_l1 < (50)::numeric) AND (foo.sic_l1 >= (40)::numeric)) THEN '6'::text WHEN ((foo.sic_l1 < (52)::numeric) AND (foo.sic_l1 >= (50)::numeric)) THEN '7'::text WHEN ((foo.sic_l1 < (60)::numeric) AND (foo.sic_l1 >= (52)::numeric)) THEN '8'::text WHEN ((foo.sic_l1 < (68)::numeric) AND (foo.sic_l1 >= (60)::numeric)) THEN '9'::text WHEN ((foo.sic_l1 < (89)::numeric) AND (foo.sic_l1 >= (70)::numeric)) THEN '10 '::text WHEN (foo.sic_l1 < (1)::numeric) THEN '11'::text WHEN (foo.sic_l1 >= (89)::numeric) THEN '12'::text ELSE NULL::text END AS division_no FROM accession, (SELECT to_number(to_char((accession.standard_industrial_classification / 100), '99'::text), '99'::text) AS sic_l1, accession.accession_id FROM accession) foo WHERE (accession.accession_id = foo.accession_id)) foo2 WHERE (foo2.accession_id = accession.accession_id);


ALTER TABLE public.accession_industry_div OWNER TO postgres;

--
-- Name: accession_timestamp; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE accession_timestamp (
    accession_id integer NOT NULL,
    creation_time timestamp with time zone DEFAULT now()
);


ALTER TABLE public.accession_timestamp OWNER TO postgres;

--
-- Name: seq_attribute_value; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE seq_attribute_value
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.seq_attribute_value OWNER TO postgres;

--
-- Name: attribute_value; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE attribute_value (
    attribute_value_id integer DEFAULT nextval('seq_attribute_value'::regclass) NOT NULL,
    qname_id integer NOT NULL,
    text_value character varying(256) NOT NULL
);


ALTER TABLE public.attribute_value OWNER TO postgres;

--
-- Name: seq_custom_role_type; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE seq_custom_role_type
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.seq_custom_role_type OWNER TO postgres;

--
-- Name: custom_role_type; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE custom_role_type (
    custom_role_type_id integer DEFAULT nextval('seq_custom_role_type'::regclass) NOT NULL,
    uri_id integer NOT NULL,
    definition character varying(2048),
    document_id integer NOT NULL
);


ALTER TABLE public.custom_role_type OWNER TO postgres;

--
-- Name: seq_document; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE seq_document
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.seq_document OWNER TO postgres;

--
-- Name: document; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE document (
    document_id integer DEFAULT nextval('seq_document'::regclass) NOT NULL,
    document_uri character varying(2048) NOT NULL
);


ALTER TABLE public.document OWNER TO postgres;

--
-- Name: seq_element; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE seq_element
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.seq_element OWNER TO postgres;

--
-- Name: element; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE element (
    element_id integer DEFAULT nextval('seq_element'::regclass) NOT NULL,
    qname_id integer NOT NULL,
    datatype_qname_id integer,
    xbrl_base_datatype_qname_id integer,
    balance_id smallint,
    period_type_id smallint NOT NULL,
    substitution_group_qname_id integer,
    abstract boolean NOT NULL,
    nillable boolean NOT NULL,
    document_id integer NOT NULL,
    is_numeric boolean NOT NULL,
    is_monetary boolean NOT NULL
);


ALTER TABLE public.element OWNER TO postgres;

--
-- Name: COLUMN element.balance_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN element.balance_id IS '1=Debit; 2=Credit';


--
-- Name: COLUMN element.period_type_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN element.period_type_id IS '1=Instant; 2=Duration; 3=Forever';


--
-- Name: seq_entity; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE seq_entity
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.seq_entity OWNER TO postgres;

--
-- Name: entity; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE entity (
    entity_id integer DEFAULT nextval('seq_entity'::regclass) NOT NULL,
    entity_code character varying NOT NULL,
    authority_scheme character varying NOT NULL,
    entity_name character varying NOT NULL
);


ALTER TABLE public.entity OWNER TO postgres;

--
-- Name: COLUMN entity.entity_code; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN entity.entity_code IS 'This will be the CIK';


--
-- Name: seq_network; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE seq_network
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.seq_network OWNER TO postgres;

--
-- Name: network; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE network (
    network_id integer DEFAULT nextval('seq_network'::regclass) NOT NULL,
    accession_id integer NOT NULL,
    extended_link_qname_id integer NOT NULL,
    extended_link_role_uri_id integer NOT NULL,
    arc_qname_id integer NOT NULL,
    arcrole_uri_id integer NOT NULL,
    description text
);


ALTER TABLE public.network OWNER TO postgres;

--
-- Name: seq_qname; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE seq_qname
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.seq_qname OWNER TO postgres;

--
-- Name: qname; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE qname (
    qname_id integer DEFAULT nextval('seq_qname'::regclass) NOT NULL,
    namespace character varying(1024),
    local_name character varying(1024) NOT NULL
);


ALTER TABLE public.qname OWNER TO postgres;

--
-- Name: seq_uri; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE seq_uri
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.seq_uri OWNER TO postgres;

--
-- Name: uri; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE uri (
    uri_id integer DEFAULT nextval('seq_uri'::regclass) NOT NULL,
    uri character varying(1028) NOT NULL
);


ALTER TABLE public.uri OWNER TO postgres;

--
-- Name: calculation_view; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW calculation_view AS
    SELECT entity.entity_id, entity.entity_name, accession.accession_id, accession.filing_accession_number, to_document.document_id, to_document.document_uri, elqname.namespace AS extended_link_namespace, elqname.local_name AS extended_link_local_name, elruri.uri AS extended_link_role_uri, custom_role_type.definition AS extended_link_role_title, arcqname.namespace AS arc_namespace, arcqname.local_name AS arc_local_name, arcroleuri.uri AS arcrole_uri, from_qname.namespace AS from_namespace, from_qname.local_name AS from_local_name, to_qname.namespace AS to_namespace, to_qname.local_name AS to_local_name, relationship.reln_order, relationship.tree_sequence, relationship.tree_depth FROM ((((((((((((((((relationship JOIN network ON ((network.network_id = relationship.network_id))) JOIN accession ON ((network.accession_id = accession.accession_id))) JOIN accession_document_association from_ada ON ((from_ada.accession_id = accession.accession_id))) JOIN accession_document_association to_ada ON ((to_ada.accession_id = accession.accession_id))) JOIN document to_document ON ((to_ada.document_id = to_document.document_id))) JOIN qname elqname ON ((network.extended_link_qname_id = elqname.qname_id))) JOIN uri elruri ON ((network.extended_link_role_uri_id = elruri.uri_id))) JOIN qname arcqname ON ((network.arc_qname_id = arcqname.qname_id))) JOIN uri arcroleuri ON ((network.arcrole_uri_id = arcroleuri.uri_id))) JOIN element from_element ON (((from_element.document_id = from_ada.document_id) AND (relationship.from_element_id = from_element.element_id)))) JOIN qname from_qname ON ((from_element.qname_id = from_qname.qname_id))) JOIN element to_element ON (((to_element.document_id = to_ada.document_id) AND (relationship.to_element_id = to_element.element_id)))) JOIN qname to_qname ON ((to_element.qname_id = to_qname.qname_id))) JOIN entity ON ((accession.entity_id = entity.entity_id))) JOIN accession_document_association cr_ada ON ((cr_ada.accession_id = accession.accession_id))) JOIN custom_role_type ON (((custom_role_type.uri_id = network.extended_link_role_uri_id) AND (custom_role_type.document_id = cr_ada.document_id)))) WHERE ((arcqname.local_name)::text = 'calculationArc'::text) ORDER BY entity.entity_id, accession.accession_id, custom_role_type.definition, relationship.tree_sequence;


ALTER TABLE public.calculation_view OWNER TO postgres;

--
-- Name: config; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE config (
    keyword character varying NOT NULL,
    value_numeric numeric,
    value_string character varying
);


ALTER TABLE public.config OWNER TO postgres;

--
-- Name: context_aug; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE context_aug (
    context_id integer NOT NULL,
    fiscal_year integer,
    fiscal_period character varying,
    context_hash bytea,
    dimension_hash bytea,
    calendar_year integer,
    calendar_period character varying,
    calendar_start_offset numeric,
    calendar_end_offset numeric,
    calendar_period_size_diff_percentage double precision
);


ALTER TABLE public.context_aug OWNER TO postgres;

--
-- Name: seq_context_dimension; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE seq_context_dimension
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.seq_context_dimension OWNER TO postgres;

--
-- Name: context_dimension; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE context_dimension (
    context_dimension_id integer DEFAULT nextval('seq_context_dimension'::regclass) NOT NULL,
    context_id integer NOT NULL,
    dimension_qname_id integer NOT NULL,
    member_qname_id integer,
    typed_qname_id integer,
    is_default boolean NOT NULL,
    is_segment boolean,
    typed_text_content text
);


ALTER TABLE public.context_dimension OWNER TO postgres;

--
-- Name: seq_custom_arcrole_type; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE seq_custom_arcrole_type
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.seq_custom_arcrole_type OWNER TO postgres;

--
-- Name: custom_arcrole_type; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE custom_arcrole_type (
    custom_arcrole_type_id integer DEFAULT nextval('seq_custom_arcrole_type'::regclass) NOT NULL,
    document_id integer NOT NULL,
    uri_id integer NOT NULL,
    definition character varying(2048),
    cycles_allowed smallint NOT NULL
);


ALTER TABLE public.custom_arcrole_type OWNER TO postgres;

--
-- Name: COLUMN custom_arcrole_type.cycles_allowed; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN custom_arcrole_type.cycles_allowed IS '1 = any; 2 = undirected; 3 = none (only applicable to arcroles)';


--
-- Name: seq_custom_arcrole_used_on; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE seq_custom_arcrole_used_on
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.seq_custom_arcrole_used_on OWNER TO postgres;

--
-- Name: custom_arcrole_used_on; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE custom_arcrole_used_on (
    custom_arcrole_used_on_id integer DEFAULT nextval('seq_custom_arcrole_used_on'::regclass) NOT NULL,
    custom_arcrole_type_id integer NOT NULL,
    qname_id integer NOT NULL
);


ALTER TABLE public.custom_arcrole_used_on OWNER TO postgres;

--
-- Name: seq_custom_role_used_on; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE seq_custom_role_used_on
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.seq_custom_role_used_on OWNER TO postgres;

--
-- Name: custom_role_used_on; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE custom_role_used_on (
    custom_role_used_on_id integer DEFAULT nextval('seq_custom_role_used_on'::regclass) NOT NULL,
    custom_role_type_id integer NOT NULL,
    qname_id integer NOT NULL
);


ALTER TABLE public.custom_role_used_on OWNER TO postgres;

--
-- Name: definition_view; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW definition_view AS
    SELECT entity.entity_id, entity.entity_name, accession.accession_id, accession.filing_accession_number, to_document.document_id, to_document.document_uri, elqname.namespace AS extended_link_namespace, elqname.local_name AS extended_link_local_name, elruri.uri AS extended_link_role_uri, custom_role_type.definition AS extended_link_role_title, arcqname.namespace AS arc_namespace, arcqname.local_name AS arc_local_name, arcroleuri.uri AS arcrole_uri, from_qname.namespace AS from_namespace, from_qname.local_name AS from_local_name, to_qname.namespace AS to_namespace, to_qname.local_name AS to_local_name, relationship.reln_order, relationship.tree_sequence, relationship.tree_depth FROM ((((((((((((((((relationship JOIN network ON ((network.network_id = relationship.network_id))) JOIN accession ON ((network.accession_id = accession.accession_id))) JOIN accession_document_association from_ada ON ((from_ada.accession_id = accession.accession_id))) JOIN accession_document_association to_ada ON ((to_ada.accession_id = accession.accession_id))) JOIN document to_document ON ((to_ada.document_id = to_document.document_id))) JOIN qname elqname ON ((network.extended_link_qname_id = elqname.qname_id))) JOIN uri elruri ON ((network.extended_link_role_uri_id = elruri.uri_id))) JOIN qname arcqname ON ((network.arc_qname_id = arcqname.qname_id))) JOIN uri arcroleuri ON ((network.arcrole_uri_id = arcroleuri.uri_id))) JOIN element from_element ON (((from_element.document_id = from_ada.document_id) AND (relationship.from_element_id = from_element.element_id)))) JOIN qname from_qname ON ((from_element.qname_id = from_qname.qname_id))) JOIN element to_element ON (((to_element.document_id = to_ada.document_id) AND (relationship.to_element_id = to_element.element_id)))) JOIN qname to_qname ON ((to_element.qname_id = to_qname.qname_id))) JOIN entity ON ((accession.entity_id = entity.entity_id))) JOIN accession_document_association cr_ada ON ((cr_ada.accession_id = accession.accession_id))) JOIN custom_role_type ON (((custom_role_type.uri_id = network.extended_link_role_uri_id) AND (custom_role_type.document_id = cr_ada.document_id)))) WHERE (((arcqname.local_name)::text <> 'calculationArc'::text) AND ((arcqname.local_name)::text <> 'presentationArc'::text)) ORDER BY entity.entity_id, accession.accession_id, custom_role_type.definition, relationship.tree_sequence;


ALTER TABLE public.definition_view OWNER TO postgres;

--
-- Name: seq_element_attribute; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE seq_element_attribute
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.seq_element_attribute OWNER TO postgres;

--
-- Name: element_attribute; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE element_attribute (
    element_attribute_id integer DEFAULT nextval('seq_element_attribute'::regclass) NOT NULL,
    element_id integer NOT NULL,
    value character varying,
    attribute_qname_id integer NOT NULL
);


ALTER TABLE public.element_attribute OWNER TO postgres;

--
-- Name: seq_element_attribute_value_association; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE seq_element_attribute_value_association
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.seq_element_attribute_value_association OWNER TO postgres;

--
-- Name: element_attribute_value_association; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE element_attribute_value_association (
    element_attribute_value_association_id integer DEFAULT nextval('seq_element_attribute_value_association'::regclass) NOT NULL,
    element_id integer NOT NULL,
    attribute_value_id integer NOT NULL
);


ALTER TABLE public.element_attribute_value_association OWNER TO postgres;

--
-- Name: seq_label_resource; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE seq_label_resource
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.seq_label_resource OWNER TO postgres;

--
-- Name: label_resource; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE label_resource (
    resource_id integer DEFAULT nextval('seq_label_resource'::regclass) NOT NULL,
    label text NOT NULL,
    xml_lang character varying(16)
);


ALTER TABLE public.label_resource OWNER TO postgres;

--
-- Name: seq_resource; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE seq_resource
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.seq_resource OWNER TO postgres;

--
-- Name: resource; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE resource (
    resource_id integer DEFAULT nextval('seq_resource'::regclass) NOT NULL,
    role_uri_id integer NOT NULL,
    qname_id integer NOT NULL,
    document_id integer NOT NULL,
    document_line_number integer NOT NULL,
    document_column_number integer NOT NULL
);


ALTER TABLE public.resource OWNER TO postgres;

--
-- Name: element_labels_view; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW element_labels_view AS
    SELECT entity.entity_id, entity.entity_name, accession.accession_id, accession.filing_accession_number, document.document_id, document.document_uri, element.element_id, element_qname.namespace AS element_namespace, element_qname.local_name AS element_local_name, relationship.relationship_id, label_resource.resource_id AS label_resource_id, resource.role_uri_id AS label_role_uri_id, uri.uri AS label_role_uri, label_resource.label AS element_label, label_resource.xml_lang AS element_label_lang FROM ((((((((((relationship JOIN network ON ((network.network_id = relationship.network_id))) JOIN accession ON ((network.accession_id = accession.accession_id))) JOIN accession_document_association acc_doc_assoc ON ((acc_doc_assoc.accession_id = accession.accession_id))) JOIN document ON ((acc_doc_assoc.document_id = document.document_id))) JOIN element ON ((relationship.from_element_id = element.element_id))) JOIN entity ON ((accession.entity_id = entity.entity_id))) JOIN qname element_qname ON ((element_qname.qname_id = element.qname_id))) JOIN label_resource ON ((relationship.to_resource_id = label_resource.resource_id))) JOIN resource ON ((relationship.to_resource_id = resource.resource_id))) JOIN uri ON ((uri.uri_id = resource.role_uri_id))) ORDER BY entity.entity_id, accession.accession_id, element_qname.local_name;


ALTER TABLE public.element_labels_view OWNER TO postgres;

--
-- Name: entity_name_history_entity_name_history_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE entity_name_history_entity_name_history_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.entity_name_history_entity_name_history_id_seq OWNER TO postgres;

--
-- Name: entity_name_history; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE entity_name_history (
    entity_name_history_id integer DEFAULT nextval('entity_name_history_entity_name_history_id_seq'::regclass) NOT NULL,
    entity_id integer NOT NULL,
    accession_id integer NOT NULL,
    entity_name character varying
);


ALTER TABLE public.entity_name_history OWNER TO postgres;

--
-- Name: seq_enumeration_arcrole_cycles_allowed; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE seq_enumeration_arcrole_cycles_allowed
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.seq_enumeration_arcrole_cycles_allowed OWNER TO postgres;

--
-- Name: enumeration_arcrole_cycles_allowed; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE enumeration_arcrole_cycles_allowed (
    enumeration_arcrole_cycles_allowed_id integer DEFAULT nextval('seq_enumeration_arcrole_cycles_allowed'::regclass) NOT NULL,
    description character varying(30) NOT NULL
);


ALTER TABLE public.enumeration_arcrole_cycles_allowed OWNER TO postgres;

--
-- Name: seq_enumeration_element_balance; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE seq_enumeration_element_balance
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.seq_enumeration_element_balance OWNER TO postgres;

--
-- Name: enumeration_element_balance; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE enumeration_element_balance (
    enumeration_element_balance_id integer DEFAULT nextval('seq_enumeration_element_balance'::regclass) NOT NULL,
    description character varying(30) NOT NULL
);


ALTER TABLE public.enumeration_element_balance OWNER TO postgres;

--
-- Name: seq_enumeration_element_period_type; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE seq_enumeration_element_period_type
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.seq_enumeration_element_period_type OWNER TO postgres;

--
-- Name: enumeration_element_period_type; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE enumeration_element_period_type (
    enumeration_element_period_type_id integer DEFAULT nextval('seq_enumeration_element_period_type'::regclass) NOT NULL,
    description character varying(30) NOT NULL
);


ALTER TABLE public.enumeration_element_period_type OWNER TO postgres;

--
-- Name: seq_enumeration_unit_measure_location; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE seq_enumeration_unit_measure_location
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.seq_enumeration_unit_measure_location OWNER TO postgres;

--
-- Name: enumeration_unit_measure_location; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE enumeration_unit_measure_location (
    enumeration_unit_measure_location_id integer DEFAULT nextval('seq_enumeration_unit_measure_location'::regclass) NOT NULL,
    description character varying(30) NOT NULL
);


ALTER TABLE public.enumeration_unit_measure_location OWNER TO postgres;

--
-- Name: seq_fact; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE seq_fact
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.seq_fact OWNER TO postgres;

--
-- Name: fact; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--
-- HF: modified to accept tuples by adding tuple_fact_id and
--      context_id, is_precision_infinity, isdecimals_infinity now NULLable

CREATE TABLE fact (
    fact_id integer DEFAULT nextval('seq_fact'::regclass) NOT NULL,
    accession_id integer NOT NULL,
    tuple_fact_id integer,
    context_id integer,
    unit_id integer,
    element_id integer NOT NULL,
    effective_value numeric,
    fact_value text,
    xml_id character varying(2048),
    precision_value integer,
    decimals_value integer,
    is_precision_infinity boolean DEFAULT false,
    is_decimals_infinity boolean DEFAULT false,
    ultimus_index integer,
    calendar_ultimus_index integer,
    uom character varying,
    is_extended boolean,
    fiscal_year integer,
    fiscal_period character varying,
    calendar_year integer,
    calendar_period character varying
);
ALTER TABLE ONLY fact ALTER COLUMN accession_id SET STATISTICS 5000;
ALTER TABLE ONLY fact ALTER COLUMN element_id SET STATISTICS 5000;


ALTER TABLE public.fact OWNER TO postgres;

--
-- Name: fact_aug; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE fact_aug (
    fact_id integer NOT NULL,
    fact_hash bytea NOT NULL,
    ultimus_index integer,
    current_index integer,
    calendar_hash bytea,
    calendar_ultimus_index integer,
    uom character varying,
    is_extended boolean
);


ALTER TABLE public.fact_aug OWNER TO postgres;

--
-- Name: fact_dei_view; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW fact_dei_view AS
    SELECT qname.local_name, qname.namespace, entity.entity_name, entity.entity_code, entity.entity_id, dimension.axis, dimension.member, fact.fact_value, fact.effective_value AS amount, context.period_start, context.period_end, context.period_instant, accession.filing_date, accession.filing_accession_number, accession.accession_id FROM qname, element, fact, entity, accession, (context LEFT JOIN (SELECT axis_qname.local_name AS axis, member_qname.local_name AS member, context_dimension.context_id FROM context_dimension, qname axis_qname, qname member_qname WHERE (((context_dimension.is_segment = true) AND (axis_qname.qname_id = context_dimension.dimension_qname_id)) AND (member_qname.qname_id = context_dimension.member_qname_id))) dimension ON ((context.context_id = dimension.context_id))) WHERE ((((((qname.qname_id = element.qname_id) AND ("substring"((qname.namespace)::text, '[^0-9]*'::text) = 'http://xbrl.us/dei/'::text)) AND (element.element_id = fact.element_id)) AND (fact.accession_id = accession.accession_id)) AND (accession.entity_id = entity.entity_id)) AND (fact.context_id = context.context_id));


ALTER TABLE public.fact_dei_view OWNER TO postgres;

--
-- Name: seq_unit; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE seq_unit
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.seq_unit OWNER TO postgres;

--
-- Name: seq_unit_measure; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE seq_unit_measure
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.seq_unit_measure OWNER TO postgres;

--
-- Name: unit; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE unit (
    unit_id integer DEFAULT nextval('seq_unit'::regclass) NOT NULL,
    accession_id integer NOT NULL,
    unit_xml_id character varying(2048) NOT NULL
);


ALTER TABLE public.unit OWNER TO postgres;

--
-- Name: unit_measure; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE unit_measure (
    unit_measure_id integer DEFAULT nextval('seq_unit_measure'::regclass) NOT NULL,
    unit_id integer NOT NULL,
    qname_id integer NOT NULL,
    location_id smallint
);


ALTER TABLE public.unit_measure OWNER TO postgres;

--
-- Name: COLUMN unit_measure.location_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN unit_measure.location_id IS '1 = measure; 2 = numerator; 3 = denominator';


--
-- Name: fact_element_view; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW fact_element_view AS
    SELECT entity.entity_id, entity.entity_name, accession.accession_id, accession.filing_accession_number, context.context_id, context.context_xml_id, context.period_start, context.period_end, context.period_instant, context_dimension.context_dimension_id, contextdimensionqname.local_name AS context_dimension_qname, contextdimensionmemberqname.local_name AS dimension_member_qname, element.element_id, elementqname.local_name AS element_qname, elementbasedatatypeqname.local_name AS element_base_datatype, elementdatatypeqname.local_name AS element_datatype, elementsubgroupqname.local_name AS element_substitution_group, enumeration_element_balance.description AS balance, enumeration_element_period_type.description AS period_type, element.abstract, element.nillable, fact.fact_id, fact.fact_value, unit.unit_id, unit.unit_xml_id, unit_measure.unit_measure_id, unitmeasureqname.local_name AS unit_measure_qname, enumeration_unit_measure_location.description AS location FROM (((((((((((((((((fact JOIN accession ON ((fact.accession_id = accession.accession_id))) JOIN entity ON ((accession.entity_id = entity.entity_id))) JOIN element ON ((fact.element_id = element.element_id))) JOIN qname elementqname ON ((element.qname_id = elementqname.qname_id))) JOIN qname elementbasedatatypeqname ON ((element.xbrl_base_datatype_qname_id = elementbasedatatypeqname.qname_id))) JOIN qname elementdatatypeqname ON ((element.datatype_qname_id = elementdatatypeqname.qname_id))) JOIN qname elementsubgroupqname ON ((element.substitution_group_qname_id = elementsubgroupqname.qname_id))) JOIN context ON ((fact.context_id = context.context_id))) JOIN enumeration_element_balance ON ((enumeration_element_balance.enumeration_element_balance_id = element.balance_id))) JOIN enumeration_element_period_type ON ((enumeration_element_period_type.enumeration_element_period_type_id = element.period_type_id))) LEFT JOIN context_dimension ON ((context_dimension.context_id = context.context_id))) LEFT JOIN qname contextdimensionqname ON ((context_dimension.dimension_qname_id = contextdimensionqname.qname_id))) LEFT JOIN qname contextdimensionmemberqname ON ((context_dimension.member_qname_id = contextdimensionmemberqname.qname_id))) LEFT JOIN unit ON ((fact.unit_id = unit.unit_id))) LEFT JOIN unit_measure ON ((unit_measure.unit_id = unit.unit_id))) LEFT JOIN qname unitmeasureqname ON ((unit_measure.qname_id = unitmeasureqname.qname_id))) LEFT JOIN enumeration_unit_measure_location ON ((enumeration_unit_measure_location.enumeration_unit_measure_location_id = unit_measure.location_id))) ORDER BY entity.entity_id, accession.accession_id, context.context_id, elementqname.local_name;


ALTER TABLE public.fact_element_view OWNER TO postgres;

--
-- Name: industry_industry_id_seq1; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE industry_industry_id_seq1
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.industry_industry_id_seq1 OWNER TO postgres;

--
-- Name: industry; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE industry (
    industry_id integer DEFAULT nextval('industry_industry_id_seq1'::regclass) NOT NULL,
    industry_classification character varying,
    industry_code integer,
    industry_description character varying,
    depth integer,
    parent_id integer
);


ALTER TABLE public.industry OWNER TO postgres;

--
-- Name: industry_level_industry_level_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE industry_level_industry_level_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.industry_level_industry_level_id_seq OWNER TO postgres;

--
-- Name: industry_level; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE industry_level (
    industry_level_id integer DEFAULT nextval('industry_level_industry_level_id_seq'::regclass) NOT NULL,
    industry_classification character varying,
    ancestor_id integer,
    ancestor_code integer,
    ancestor_depth integer,
    descendant_id integer,
    descendant_code integer,
    descendant_depth integer
);


ALTER TABLE public.industry_level OWNER TO postgres;

--
-- Name: industry_structure_industry_structure_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE industry_structure_industry_structure_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.industry_structure_industry_structure_id_seq OWNER TO postgres;

--
-- Name: industry_structure; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE industry_structure (
    industry_structure_id integer DEFAULT nextval('industry_structure_industry_structure_id_seq'::regclass) NOT NULL,
    industry_classification character varying NOT NULL,
    depth integer NOT NULL,
    level_name character varying
);


ALTER TABLE public.industry_structure OWNER TO postgres;

--
-- Name: namespace_namespace_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE namespace_namespace_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.namespace_namespace_id_seq OWNER TO postgres;

--
-- Name: namespace; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE namespace (
    namespace_id integer DEFAULT nextval('namespace_namespace_id_seq'::regclass) NOT NULL,
    uri character varying NOT NULL,
    is_base boolean NOT NULL,
    taxonomy_version_id integer,
    prefix character varying,
    name character varying
);


ALTER TABLE public.namespace OWNER TO postgres;

--
-- Name: period_fact_element_view; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW period_fact_element_view AS
    SELECT en.entity_name, en.entity_code, qc.local_name, qa.local_name AS axis, qm.local_name AS member, f.effective_value AS amount, (ca.fiscal_year)::double precision AS year, a.filing_date, a.restatement_index, a.accession_id, qc.namespace, f.fact_id, (ca.fiscal_period)::text AS period, uom(f.unit_id) AS uom FROM (((((((((fact f JOIN accession a ON ((f.accession_id = a.accession_id))) JOIN element ec ON ((f.element_id = ec.element_id))) JOIN qname qc ON ((ec.qname_id = qc.qname_id))) JOIN entity en ON ((en.entity_id = a.entity_id))) JOIN context c ON ((f.context_id = c.context_id))) JOIN context_aug ca ON ((c.context_id = ca.context_id))) LEFT JOIN context_dimension cd ON (((cd.context_id = c.context_id) AND (cd.is_segment = true)))) LEFT JOIN qname qa ON ((qa.qname_id = cd.dimension_qname_id))) LEFT JOIN qname qm ON ((qm.qname_id = cd.member_qname_id)));


ALTER TABLE public.period_fact_element_view OWNER TO postgres;

--
-- Name: presentation_view; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW presentation_view AS
    SELECT entity.entity_id, entity.entity_name, accession.accession_id, accession.filing_accession_number, to_document.document_id, to_document.document_uri, elqname.namespace AS extended_link_namespace, elqname.local_name AS extended_link_local_name, elruri.uri AS extended_link_role_uri, custom_role_type.definition AS extended_link_role_title, arcqname.namespace AS arc_namespace, arcqname.local_name AS arc_local_name, arcroleuri.uri AS arcrole_uri, from_qname.namespace AS from_namespace, from_qname.local_name AS from_local_name, to_qname.namespace AS to_namespace, to_qname.local_name AS to_local_name, relationship.reln_order, relationship.tree_sequence, relationship.tree_depth FROM ((((((((((((((((relationship JOIN network ON ((network.network_id = relationship.network_id))) JOIN accession ON ((network.accession_id = accession.accession_id))) JOIN accession_document_association from_ada ON ((from_ada.accession_id = accession.accession_id))) JOIN accession_document_association to_ada ON ((to_ada.accession_id = accession.accession_id))) JOIN document to_document ON ((to_ada.document_id = to_document.document_id))) JOIN qname elqname ON ((network.extended_link_qname_id = elqname.qname_id))) JOIN uri elruri ON ((network.extended_link_role_uri_id = elruri.uri_id))) JOIN qname arcqname ON ((network.arc_qname_id = arcqname.qname_id))) JOIN uri arcroleuri ON ((network.arcrole_uri_id = arcroleuri.uri_id))) JOIN element from_element ON (((from_element.document_id = from_ada.document_id) AND (relationship.from_element_id = from_element.element_id)))) JOIN qname from_qname ON ((from_element.qname_id = from_qname.qname_id))) JOIN element to_element ON (((to_element.document_id = to_ada.document_id) AND (relationship.to_element_id = to_element.element_id)))) JOIN qname to_qname ON ((to_element.qname_id = to_qname.qname_id))) JOIN entity ON ((accession.entity_id = entity.entity_id))) JOIN accession_document_association cr_ada ON ((cr_ada.accession_id = accession.accession_id))) JOIN custom_role_type ON (((custom_role_type.uri_id = network.extended_link_role_uri_id) AND (custom_role_type.document_id = cr_ada.document_id)))) WHERE ((arcqname.local_name)::text = 'presentationArc'::text) ORDER BY entity.entity_id, accession.accession_id, custom_role_type.definition, relationship.tree_sequence;


ALTER TABLE public.presentation_view OWNER TO postgres;

--
-- Name: query_log_query_log_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE query_log_query_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.query_log_query_log_id_seq OWNER TO postgres;

--
-- Name: query_log; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE query_log (
    query_log_id integer DEFAULT nextval('query_log_query_log_id_seq'::regclass) NOT NULL,
    user_name character varying,
    start_time timestamp without time zone,
    end_time timestamp without time zone,
    query character varying,
    task character varying
);


ALTER TABLE public.query_log OWNER TO postgres;

--
-- Name: seq_reference_part; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE seq_reference_part
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.seq_reference_part OWNER TO postgres;

--
-- Name: reference_part; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE reference_part (
    reference_part_id integer DEFAULT nextval('seq_reference_part'::regclass) NOT NULL,
    resource_id integer NOT NULL,
    value character varying NOT NULL,
    qname_id integer NOT NULL
);


ALTER TABLE public.reference_part OWNER TO postgres;

--
-- Name: seq_reference_part_type; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE seq_reference_part_type
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.seq_reference_part_type OWNER TO postgres;

--
-- Name: reference_part_type; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE reference_part_type (
    reference_part_type_id integer DEFAULT nextval('seq_reference_part_type'::regclass) NOT NULL,
    namespace character varying,
    local_name character varying,
    revision_id integer,
    deleted_revision_id integer
);


ALTER TABLE public.reference_part_type OWNER TO postgres;

--
-- Name: seq_reference_resource; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE seq_reference_resource
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.seq_reference_resource OWNER TO postgres;

--
-- Name: reference_resource; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE reference_resource (
    reference_resource_id integer DEFAULT nextval('seq_reference_resource'::regclass) NOT NULL,
    element_id integer,
    extended_link_role_id integer,
    resource_role_id integer,
    revision_id integer,
    deleted_revision_id integer
);


ALTER TABLE public.reference_resource OWNER TO postgres;

--
-- Name: relationship_full_view; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW relationship_full_view AS
    SELECT relationship.relationship_id, network.extended_link_qname_id AS elqname_id, elqname.namespace AS el_namespace, elqname.local_name AS el_local_name, network.extended_link_role_uri_id AS elroleuri_id, elroleuri.uri AS el_role_uri, network.arc_qname_id AS arcqname_id, arcqname.namespace AS arc_namespace, arcqname.local_name AS arc_local_name, network.arcrole_uri_id AS arcroleuri_id, arcroleuri.uri AS arcroleuri, relationship.from_element_id, from_element_qname.namespace AS from_element_namespace, from_element_qname.local_name AS from_element_name, relationship.to_element_id, to_element_qname.namespace AS to_element_namespace, to_element_qname.local_name AS to_element_name, relationship.from_resource_id, from_resource_qname.namespace AS from_resource_namespace, from_resource_qname.local_name AS from_resource_name, relationship.to_resource_id, to_resource_qname.namespace AS to_resource_namespace, to_resource_qname.local_name AS to_resource_name, relationship.reln_order AS relationship_order, relationship.calculation_weight, relationship.tree_sequence, relationship.tree_depth, accession.accession_id, entity.entity_id, entity.entity_name FROM (((((((((((((((relationship JOIN network ON ((network.network_id = relationship.network_id))) JOIN accession ON ((network.accession_id = accession.accession_id))) JOIN qname elqname ON ((network.extended_link_qname_id = elqname.qname_id))) JOIN uri elroleuri ON ((network.extended_link_role_uri_id = elroleuri.uri_id))) JOIN qname arcqname ON ((network.arc_qname_id = arcqname.qname_id))) JOIN uri arcroleuri ON ((network.arcrole_uri_id = arcroleuri.uri_id))) LEFT JOIN element from_element ON ((relationship.from_element_id = from_element.element_id))) JOIN qname from_element_qname ON ((from_element.qname_id = from_element_qname.qname_id))) FULL JOIN element to_element ON ((relationship.to_element_id = to_element.element_id))) LEFT JOIN qname to_element_qname ON ((to_element.qname_id = to_element_qname.qname_id))) FULL JOIN resource from_resource ON ((relationship.from_resource_id = from_resource.resource_id))) LEFT JOIN qname from_resource_qname ON ((from_resource.qname_id = from_resource_qname.qname_id))) FULL JOIN resource to_resource ON ((relationship.to_resource_id = to_resource.resource_id))) LEFT JOIN qname to_resource_qname ON ((to_resource.qname_id = to_resource_qname.qname_id))) JOIN entity ON ((accession.entity_id = entity.entity_id))) ORDER BY entity.entity_id, accession.accession_id, relationship.relationship_id;


ALTER TABLE public.relationship_full_view OWNER TO postgres;

--
-- Name: relationship_view; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW relationship_view AS
    SELECT relationship.relationship_id, network.extended_link_qname_id AS elqname_id, elqname.local_name AS el_local_name, network.extended_link_role_uri_id AS elroleuri_id, elroleuri.uri AS el_role_uri, network.arc_qname_id AS arcqname_id, arcqname.local_name AS arc_local_name, network.arcrole_uri_id AS arcroleuri_id, arcroleuri.uri AS arcroleuri, relationship.from_element_id, from_element_qname.local_name AS from_element_name, relationship.to_element_id, to_element_qname.local_name AS to_element_name, relationship.from_resource_id, from_resource_qname.local_name AS from_resource_name, relationship.to_resource_id, to_resource_qname.local_name AS to_resource_name, accession.accession_id, entity.entity_id, entity.entity_name FROM (((((((((((((((relationship JOIN network ON ((network.network_id = relationship.network_id))) JOIN accession ON ((network.accession_id = accession.accession_id))) JOIN qname elqname ON ((network.extended_link_qname_id = elqname.qname_id))) JOIN uri elroleuri ON ((network.extended_link_role_uri_id = elroleuri.uri_id))) JOIN qname arcqname ON ((network.arc_qname_id = arcqname.qname_id))) JOIN uri arcroleuri ON ((network.arcrole_uri_id = arcroleuri.uri_id))) LEFT JOIN element from_element ON ((relationship.from_element_id = from_element.element_id))) JOIN qname from_element_qname ON ((from_element.qname_id = from_element_qname.qname_id))) FULL JOIN element to_element ON ((relationship.to_element_id = to_element.element_id))) LEFT JOIN qname to_element_qname ON ((to_element.qname_id = to_element_qname.qname_id))) FULL JOIN resource from_resource ON ((relationship.from_resource_id = from_resource.resource_id))) LEFT JOIN qname from_resource_qname ON ((from_resource.qname_id = from_resource_qname.qname_id))) FULL JOIN resource to_resource ON ((relationship.to_resource_id = to_resource.resource_id))) LEFT JOIN qname to_resource_qname ON ((to_resource.qname_id = to_resource_qname.qname_id))) JOIN entity ON ((accession.entity_id = entity.entity_id))) ORDER BY entity.entity_id, accession.accession_id, relationship.relationship_id;


ALTER TABLE public.relationship_view OWNER TO postgres;

--
-- Name: seq_sic_code; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE seq_sic_code
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.seq_sic_code OWNER TO postgres;

--
-- Name: sic_code; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE sic_code (
    sic_code_id integer DEFAULT nextval('seq_sic_code'::regclass) NOT NULL,
    description character varying(1024) NOT NULL
);


ALTER TABLE public.sic_code OWNER TO postgres;


--
-- Name: tabular_facts_by_element; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW tabular_facts_by_element AS
    SELECT foo.entity_name, foo.entity_code, foo.axis, foo.member, foo.local_name, max(foo.y2007) AS "Y_2007", max(foo.q12008) AS "Q1_2008", max(foo.q22008) AS "Q2_2008", max(foo.q32008) AS "Q3_2008", max(foo.q42008) AS "Q4_2008", max(foo.y2008) AS "Y_2008", max(foo.q12009) AS "Q1_2009", max(foo.q22009) AS "Q2_2009", max(foo.q32009) AS "Q3_2009", max(foo.q42009) AS "Q4_2009", max(foo.y2009) AS "Y_2009", max(foo.q12010) AS "Q1_2010", max(foo.q22010) AS "Q2_2010", max(foo.q32010) AS "Q3_2010", max(foo.q42010) AS "Q4_2010", max(foo.y2010) AS "Y_2010" FROM (SELECT period_fact_element_view.entity_name, period_fact_element_view.entity_code, period_fact_element_view.axis, period_fact_element_view.member, period_fact_element_view.local_name, CASE WHEN ((period_fact_element_view.year = (2007)::double precision) AND (period_fact_element_view.period = 'Y'::text)) THEN period_fact_element_view.amount ELSE NULL::numeric END AS y2007, CASE WHEN ((period_fact_element_view.year = (2008)::double precision) AND (period_fact_element_view.period = '1Q'::text)) THEN period_fact_element_view.amount ELSE NULL::numeric END AS q12008, CASE WHEN ((period_fact_element_view.year = (2008)::double precision) AND (period_fact_element_view.period = '2Q'::text)) THEN period_fact_element_view.amount ELSE NULL::numeric END AS q22008, CASE WHEN ((period_fact_element_view.year = (2008)::double precision) AND (period_fact_element_view.period = '3Q'::text)) THEN period_fact_element_view.amount ELSE NULL::numeric END AS q32008, CASE WHEN ((period_fact_element_view.year = (2008)::double precision) AND (period_fact_element_view.period = '4Q'::text)) THEN period_fact_element_view.amount ELSE NULL::numeric END AS q42008, CASE WHEN ((period_fact_element_view.year = (2008)::double precision) AND (period_fact_element_view.period = 'Y'::text)) THEN period_fact_element_view.amount ELSE NULL::numeric END AS y2008, CASE WHEN ((period_fact_element_view.year = (2009)::double precision) AND (period_fact_element_view.period = '1Q'::text)) THEN period_fact_element_view.amount ELSE NULL::numeric END AS q12009, CASE WHEN ((period_fact_element_view.year = (2009)::double precision) AND (period_fact_element_view.period = '2Q'::text)) THEN period_fact_element_view.amount ELSE NULL::numeric END AS q22009, CASE WHEN ((period_fact_element_view.year = (2009)::double precision) AND (period_fact_element_view.period = '3Q'::text)) THEN period_fact_element_view.amount ELSE NULL::numeric END AS q32009, CASE WHEN ((period_fact_element_view.year = (2009)::double precision) AND (period_fact_element_view.period = '4Q'::text)) THEN period_fact_element_view.amount ELSE NULL::numeric END AS q42009, CASE WHEN ((period_fact_element_view.year = (2009)::double precision) AND (period_fact_element_view.period = 'Y'::text)) THEN period_fact_element_view.amount ELSE NULL::numeric END AS y2009, CASE WHEN ((period_fact_element_view.year = (2010)::double precision) AND (period_fact_element_view.period = '1Q'::text)) THEN period_fact_element_view.amount ELSE NULL::numeric END AS q12010, CASE WHEN ((period_fact_element_view.year = (2010)::double precision) AND (period_fact_element_view.period = '2Q'::text)) THEN period_fact_element_view.amount ELSE NULL::numeric END AS q22010, CASE WHEN ((period_fact_element_view.year = (2010)::double precision) AND (period_fact_element_view.period = '3Q'::text)) THEN period_fact_element_view.amount ELSE NULL::numeric END AS q32010, CASE WHEN ((period_fact_element_view.year = (2010)::double precision) AND (period_fact_element_view.period = '4Q'::text)) THEN period_fact_element_view.amount ELSE NULL::numeric END AS q42010, CASE WHEN ((period_fact_element_view.year = (2010)::double precision) AND (period_fact_element_view.period = 'Y'::text)) THEN period_fact_element_view.amount ELSE NULL::numeric END AS y2010 FROM period_fact_element_view) foo GROUP BY foo.entity_name, foo.entity_code, foo.local_name, foo.axis, foo.member;


ALTER TABLE public.tabular_facts_by_element OWNER TO postgres;

--
-- Name: taxonomy_taxonomy_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE taxonomy_taxonomy_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.taxonomy_taxonomy_id_seq OWNER TO postgres;

--
-- Name: taxonomy; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE taxonomy (
    taxonomy_id integer DEFAULT nextval('taxonomy_taxonomy_id_seq'::regclass) NOT NULL,
    name character varying NOT NULL
);


ALTER TABLE public.taxonomy OWNER TO postgres;

--
-- Name: taxonomy_version_taxonomy_version_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE taxonomy_version_taxonomy_version_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.taxonomy_version_taxonomy_version_id_seq OWNER TO postgres;

--
-- Name: taxonomy_version; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE taxonomy_version (
    taxonomy_version_id integer DEFAULT nextval('taxonomy_version_taxonomy_version_id_seq'::regclass) NOT NULL,
    taxonomy_id integer NOT NULL,
    version character varying NOT NULL
);


ALTER TABLE public.taxonomy_version OWNER TO postgres;

--
-- Data for Name: industry; Type: TABLE DATA; Schema: public; Owner: postgres
--

-- !!!!warning, can't have any ; inside labels, will terminate sql sending!!!!

INSERT INTO industry (industry_id, industry_classification, industry_code, industry_description, depth, parent_id) VALUES
(4315, 'SEC', 3576, 'Computer Communications Equipment', 4, 2424),
(4316, 'SEC', 4955, 'Hazardous Waste Management', 4, 2552),
(4317, 'SEC', 4990, 'Hazardous Waste Management', 3, 2792),
(4318, 'SEC', 4991, 'Hazardous Waste Management', 4, 4317),
(4319, 'SEC', 5412, 'Convenience Stores', 4, 2618),
(4320, 'SEC', 6170, 'Finance Lessors', 3, 2659),
(4322, 'SEC', 6180, 'Asset Backed Securities', 3, 2659),
(4323, 'SEC', 6189, 'Asset Backed Securities', 4, 4322),
(4324, 'SEC', 6190, 'Financial Services', 3, 2659),
(4325, 'SEC', 6199, 'Financial Services', 4, 4324),
(4326, 'SEC', 6532, 'Real Estate Dealers (for their own account)', 4, 2694),
(4327, 'SEC', 6770, 'Blank Checks', 3, 2703),
(4328, 'SEC', 6795, 'Mineral Royalty Traders', 4, 2704),
(4329, 'SEC', 7385, 'Telephone Interconnect Systems', 4, 2731),
(4337, 'SEC', 8880, 'American Depositary Receipts', 2, 4336),
(4338, 'SEC', 8888, 'Foreign Governments', 2, 4336),
(4339, 'SEC', 9995, 'Non-operating Establishments', 2, 4336),
(4340, 'SEC', 6172, 'Finance Lessors', 4, 4320),
(4336, 'SEC', 99, 'Miscellaneous', 1, NULL),
(1, 'NAICS', 11, 'Agriculture, Forestry, Fishing and Hunting', 1, NULL),
(132, 'NAICS', 21, 'Mining, Quarrying, and Oil and Gas Extraction', 1, NULL),
(98, 'NAICS', 113, 'Forestry and Logging', 2, 1),
(180, 'NAICS', 22, 'Utilities', 1, NULL),
(205, 'NAICS', 23, 'Construction', 1, NULL),
(278, 'NAICS', 31, 'Manufacturing', 4, NULL),
(572, 'NAICS', 327, 'Nonmetallic Mineral Product Manufacturing', 2, 278),
(700, 'NAICS', 333, 'Machinery Manufacturing', 2, 278),
(930, 'NAICS', 42, 'Wholesale Trade', 1, NULL),
(1095, 'NAICS', 44, 'Retail Trade', 4, NULL),
(1194, 'NAICS', 4482, 'Shoe Stores', 3, 1180),
(1262, 'NAICS', 48, 'Transportation and Warehousing', 4, NULL),
(1273, 'NAICS', 482, 'Rail Transportation', 2, 1262),
(1402, 'NAICS', 51, 'Information', 1, NULL),
(1480, 'NAICS', 52, 'Finance and Insurance', 1, NULL),
(1569, 'NAICS', 53, 'Real Estate and Rental and Leasing', 1, NULL),
(1624, 'NAICS', 54, 'Professional, Scientific, and Technical Services', 1, NULL),
(1591, 'NAICS', 532, 'Rental and Leasing Services', 2, 1569),
(1718, 'NAICS', 55, 'Management of Companies and Enterprises', 1, NULL),
(1725, 'NAICS', 56, 'Administrative and Support and Waste Management and Remediation Services', 1, NULL),
(1812, 'NAICS', 61, 'Educational Services', 1, NULL),
(1850, 'NAICS', 62, 'Health Care and Social Assistance', 1, NULL),
(1942, 'NAICS', 71, 'Arts, Entertainment, and Recreation', 1, NULL),
(2003, 'NAICS', 72, 'Accommodation and Food Services', 1, NULL),
(2037, 'NAICS', 81, 'Other Services (except Public Administration)', 1, NULL),
(2071, 'NAICS', 812, 'Personal and Laundry Services', 2, 2037),
(2135, 'NAICS', 92, 'Public Administration', 1, NULL),
(2900, 'SIC', 1099, 'Metal Ores, nec', 4, 2898),
(3040, 'SIC', 2099, 'Food Preparations, nec', 4, 3033),
(3162, 'SIC', 2541, 'Wood Partitions & Fixtures', 4, 3161),
(3295, 'SIC', 3161, 'Luggage', 4, 3294),
(2797, 'SEC', 90, 'Public Administration', 1, NULL),
(2789, 'SEC', 10, 'Mining', 1, NULL),
(2790, 'SEC', 15, 'Construction', 1, NULL),
(2791, 'SEC', 20, 'Manufacturing', 1, NULL),
(2792, 'SEC', 40, 'Transportation, Communications, Eletric, Gas and Sanitary Services', 1, NULL),
(2793, 'SEC', 50, 'Wholesale Trade', 1, NULL),
(2794, 'SEC', 52, 'Retail Trade', 1, NULL),
(2795, 'SEC', 60, 'Finance, Insurance, and Real Estate', 1, NULL),
(2796, 'SEC', 70, 'Services', 1, NULL),
(4314, 'SIC', 90, 'Public Administration', 1, NULL),
(4306, 'SIC', 10, 'Mining', 1, NULL),
(4307, 'SIC', 15, 'Construction', 1, NULL),
(4308, 'SIC', 20, 'Manufacturing', 1, NULL),
(4309, 'SIC', 40, 'Transportation, Communications, Eletric, Gas and Sanitary Services', 1, NULL),
(4310, 'SIC', 50, 'Wholesale Trade', 1, NULL),
(4311, 'SIC', 52, 'Retail Trade', 1, NULL),
(4312, 'SIC', 60, 'Finance, Insurance, and Real Estate', 1, NULL),
(4313, 'SIC', 70, 'Services', 1, NULL),
(2788, 'SEC', 1, 'Agriculture, Forestry, And Fishing', 1, NULL),
(4305, 'SIC', 1, 'Agriculture, Forestry, And Fishing', 1, NULL),
(2513, 'SEC', 4010, 'Railroads', 3, 2512),
(2799, 'SIC', 110, 'Cash Grains', 3, 2798),
(3420, 'SIC', 3510, 'Engines & Turbines', 3, 3419),
(2868, 'SIC', 800, 'FORESTRY', 2, 4305),
(2804, 'SIC', 119, 'Cash Grains, nec', 4, 2799),
(2800, 'SIC', 111, 'Wheat', 4, 2799),
(2801, 'SIC', 112, 'Rice', 4, 2799),
(2802, 'SIC', 115, 'Corn', 4, 2799),
(2803, 'SIC', 116, 'Soybeans', 4, 2799),
(2810, 'SIC', 139, 'Field Crops, Except Cash Grains, nec', 4, 2805),
(2809, 'SIC', 134, 'Potato Growers', 4, 2805),
(2808, 'SIC', 133, 'Sugarcane And Sugar Beets', 4, 2805),
(2807, 'SIC', 132, 'Tobacco Growers', 4, 2805),
(2806, 'SIC', 131, 'Cotton', 4, 2805),
(2812, 'SIC', 161, 'Vegetables And Melons', 4, 2811),
(2814, 'SIC', 171, 'Berry Crops', 4, 2813),
(2815, 'SIC', 172, 'Grapes/Vineyards', 4, 2813),
(2816, 'SIC', 173, 'Tree Nuts', 4, 2813),
(2214, 'SEC', 900, 'FISHING, HUNTING & TRAPPING', 2, 2788),
(2213, 'SEC', 800, 'FORESTRY', 2, 2788),
(105, 'NAICS', 1133, 'Logging', 3, 98),
(368, 'NAICS', 313, 'Textile Mills', 2, 278),
(2817, 'SIC', 174, 'Citrus Fruits', 4, 2813),
(2818, 'SIC', 175, 'Deciduous Tree Fruits/Orchards', 4, 2813),
(2819, 'SIC', 179, 'Fruits & Tree Nuts, nec', 4, 2813),
(2821, 'SIC', 181, 'Ornamental Nursery Products', 4, 2820),
(2822, 'SIC', 182, 'Food Crops Grown Under Cover', 4, 2820),
(2824, 'SIC', 191, 'General Farms, Primarily Crop', 4, 2823),
(2829, 'SIC', 213, 'Hogs', 4, 2826),
(2877, 'SIC', 912, 'Finfish', 4, 2876),
(2830, 'SIC', 214, 'Sheep & Goats', 4, 2826),
(2828, 'SIC', 212, 'Beef Cattle, Except Feedlots', 4, 2826),
(2827, 'SIC', 211, 'Beef Cattle Feedlots', 4, 2826),
(2831, 'SIC', 219, 'General Livestock, Except Dairy/Poultry', 4, 2826),
(2833, 'SIC', 241, 'Dairy Farms', 4, 2832),
(2978, 'SIC', 1794, 'Excavation Work', 4, 2975),
(2979, 'SIC', 1795, 'Wrecking & Demolition Work', 4, 2975),
(2980, 'SIC', 1796, 'Installing Building Equipment, nec', 4, 2975),
(2981, 'SIC', 1799, 'Special Trade Contractors, nec', 4, 2975),
(2976, 'SIC', 1791, 'Structural Steel Erection', 4, 2975),
(2242, 'SEC', 2011, 'Meat Packing Plants', 4, 2241),
(2244, 'SEC', 2015, 'Poultry Slaughtering & Processing', 4, 2241),
(2243, 'SEC', 2013, 'Sausages & Other Prepared Meats', 4, 2241),
(2984, 'SIC', 2011, 'Meat Packing Plants', 4, 2983),
(2986, 'SIC', 2015, 'Poultry Slaughtering & Processing', 4, 2983),
(2985, 'SIC', 2013, 'Sausages & Other Prepared Meats', 4, 2983),
(2246, 'SEC', 2024, 'Ice Cream & Frozen Desserts', 4, 2245),
(2990, 'SIC', 2023, 'Dry, Condensed & Evaporated Products', 4, 2987),
(2991, 'SIC', 2024, 'Ice Cream & Frozen Desserts', 4, 2987),
(2989, 'SIC', 2022, 'Cheese, Natural & Processed', 4, 2987),
(2988, 'SIC', 2021, 'Creamery Butter', 4, 2987),
(2992, 'SIC', 2026, 'Fluid Milk', 4, 2987),
(2248, 'SEC', 2033, 'Canned Fruits & Vegetables', 4, 2247),
(2999, 'SIC', 2038, 'Frozen Specialties, nec', 4, 2993),
(2994, 'SIC', 2032, 'Canned Specialties', 4, 2993),
(2998, 'SIC', 2037, 'Frozen Fruits & Vegetables', 4, 2993),
(2997, 'SIC', 2035, 'Pickles, Sauces & Salad Dressings', 4, 2993),
(2607, 'SEC', 5211, 'Lumber & Other Building Materials', 4, 2606),
(3806, 'SIC', 5211, 'Lumber & Other Building Materials', 4, 3805),
(3808, 'SIC', 5231, 'Paint, Glass & Wallpaper Stores', 4, 3807),
(3810, 'SIC', 5251, 'Hardware Stores', 4, 3809),
(3812, 'SIC', 5261, 'Retail Nurseries & Garden Stores', 4, 3811),
(2609, 'SEC', 5271, 'Mobile Homes Dealers', 4, 2608),
(3814, 'SIC', 5271, 'Mobile Homes Dealers', 4, 3813),
(2612, 'SEC', 5311, 'Department Stores', 4, 2611),
(3817, 'SIC', 5311, 'Department Stores', 4, 3816),
(2614, 'SEC', 5331, 'Variety Stores', 4, 2613),
(3819, 'SIC', 5331, 'Variety Stores', 4, 3818),
(2616, 'SEC', 5399, 'Miscellaneous General Merchandise Stores', 4, 2615),
(3821, 'SIC', 5399, 'Miscellaneous General Merchandise Stores', 4, 3820),
(2619, 'SEC', 5411, 'Grocery Stores', 4, 2618),
(3824, 'SIC', 5411, 'Grocery Stores', 4, 3823),
(3826, 'SIC', 5421, 'Meat & Fish Markets', 4, 3825),
(3828, 'SIC', 5431, 'Fruit & Vegetable Markets', 4, 3827),
(3830, 'SIC', 5441, 'Candy, Nut & Confectionery Stores', 4, 3829),
(3832, 'SIC', 5451, 'Dairy Products Stores', 4, 3831),
(3834, 'SIC', 5461, 'Retail Bakeries', 4, 3833),
(3836, 'SIC', 5499, 'Miscellaneous Food Stores', 4, 3835),
(3839, 'SIC', 5511, 'New & Used Car Dealers', 4, 3838),
(3841, 'SIC', 5521, 'Used Car Dealers', 4, 3840),
(2622, 'SEC', 5531, 'Auto & Home Supply Stores', 4, 2621),
(3919, 'SIC', 6011, 'Federal Reserve Banks', 4, 3918),
(2711, 'SEC', 7011, 'Hotels & Motels', 4, 2710),
(4009, 'SIC', 7011, 'Hotels & Motels', 4, 4008),
(4011, 'SIC', 7021, 'Rooming & Boarding Houses', 4, 4010),
(4013, 'SIC', 7032, 'Sporting & Recreational Camps', 4, 4012),
(4014, 'SIC', 7033, 'Trailer Parks & Campsites', 4, 4012),
(4016, 'SIC', 7041, 'Membership Basis Organization Hotels', 4, 4015),
(4024, 'SIC', 7217, 'Carpet & Upholstery Cleaners', 4, 4018),
(4020, 'SIC', 7212, 'Garment Pressing & Cleaners'' Agents', 4, 4018),
(4021, 'SIC', 7213, 'Linen Supply', 4, 4018),
(4022, 'SIC', 7215, 'Coin-Operated Laundries & Cleaning', 4, 4018),
(4023, 'SIC', 7216, 'Drycleaning Plants, Except Rug', 4, 4018),
(12, 'NAICS', 111150, 'Corn Farming', 5, 13),
(107, 'NAICS', 11331, 'Logging', 4, 105),
(1151, 'NAICS', 44521, 'Meat Markets', 4, 1149),
(1773, 'NAICS', 561622, 'Locksmiths', 5, 1771),
(2315, 'SEC', 2770, 'Greeting Cards', 3, 2302),
(2860, 'SIC', 752, 'Animal Specialty Services', 4, 2858),
(2837, 'SIC', 253, 'Turkey Farms', 4, 2834),
(2839, 'SIC', 259, 'Poultry & Eggs, nec', 4, 2834),
(2838, 'SIC', 254, 'Poultry Farms', 4, 2834),
(2836, 'SIC', 252, 'Chicken Eggs', 4, 2834),
(2835, 'SIC', 251, 'Broiler, Fryer & Roaster Chickens', 4, 2834),
(2843, 'SIC', 273, 'Aquaculture', 4, 2840),
(2844, 'SIC', 279, 'Animal Specialties, nec', 4, 2840),
(2841, 'SIC', 271, 'Fur Bearing Animals & Rabbits', 4, 2840),
(2842, 'SIC', 272, 'Horses & Other Equines', 4, 2840),
(2846, 'SIC', 291, 'General Farms, Primarily Animal', 4, 2845),
(2849, 'SIC', 711, 'Soil Preparation Services', 4, 2848),
(2854, 'SIC', 724, 'Cotton Ginning', 4, 2850),
(2853, 'SIC', 723, 'Crop Preparation Services For Market', 4, 2850),
(2851, 'SIC', 721, 'Crop Planting & Protecting', 4, 2850),
(2852, 'SIC', 722, 'Crop Harvesting', 4, 2850),
(2856, 'SIC', 741, 'Veterinary Services for Livestock', 4, 2855),
(2857, 'SIC', 742, 'Veterinary Services, Specialties', 4, 2855),
(2859, 'SIC', 751, 'Livestock Services, Except Veterinary', 4, 2858),
(2862, 'SIC', 761, 'Farm Labor Contractors', 4, 2861),
(2863, 'SIC', 762, 'Farm Management Services', 4, 2861),
(2866, 'SIC', 782, 'Lawn & Garden Services', 4, 2864),
(2867, 'SIC', 783, 'Ornamental Shrub & Tree Services', 4, 2864),
(2865, 'SIC', 781, 'Landscape Counseling & Planning', 4, 2864),
(2870, 'SIC', 811, 'Timber Tracts', 4, 2869),
(2872, 'SIC', 831, 'Forest Products', 4, 2871),
(2874, 'SIC', 851, 'Forestry Services', 4, 2873),
(2879, 'SIC', 919, 'Miscellaneous Marine Products', 4, 2876),
(2878, 'SIC', 913, 'Shellfish', 4, 2876),
(2881, 'SIC', 921, 'Fish Hatcheries & Preserves', 4, 2880),
(2883, 'SIC', 971, 'Hunting, Trapping & Game Propagation', 4, 2882),
(2886, 'SIC', 1011, 'Iron Ores', 4, 2885),
(2888, 'SIC', 1021, 'Copper Ores', 4, 2887),
(2890, 'SIC', 1031, 'Lead & Zinc Ores', 4, 2889),
(2893, 'SIC', 1044, 'Silver Ores', 4, 2891),
(2892, 'SIC', 1041, 'Gold Ores', 4, 2891),
(2895, 'SIC', 1061, 'Ferroalloy Ores, Except Vanadium', 4, 2894),
(2223, 'SEC', 1311, 'Crude Petroleum & Natural Gas', 4, 2222),
(2911, 'SIC', 1311, 'Crude Petroleum & Natural Gas', 4, 2910),
(2913, 'SIC', 1321, 'Natural Gas Liquids', 4, 2912),
(2226, 'SEC', 1382, 'Oil & Gas Exploration Services', 4, 2224),
(2227, 'SEC', 1389, 'Oil & Gas Field Services, nec', 4, 2224),
(2225, 'SEC', 1381, 'Drilling Oil & Gas Wells', 4, 2224),
(2917, 'SIC', 1389, 'Oil & Gas Field Services, nec', 4, 2914),
(2915, 'SIC', 1381, 'Drilling Oil & Gas Wells', 4, 2914),
(2916, 'SIC', 1382, 'Oil & Gas Exploration Services', 4, 2914),
(2920, 'SIC', 1411, 'Dimension Stone', 4, 2919),
(2924, 'SIC', 1429, 'Crushed & Broken Stone, nec', 4, 2921),
(2922, 'SIC', 1422, 'Crushed & Broken Limestone', 4, 2921),
(2923, 'SIC', 1423, 'Crushed & Broken Granite', 4, 2921),
(2926, 'SIC', 1442, 'Construction Sand & Gravel', 4, 2925),
(2927, 'SIC', 1446, 'Industrial Sand', 4, 2925),
(2929, 'SIC', 1455, 'Kaolin & Ball Clay', 4, 2928),
(2930, 'SIC', 1459, 'Clay & Related Minerals, nec', 4, 2928),
(2934, 'SIC', 1479, 'Chemical & Fertilizer Mining nec', 4, 2931),
(2932, 'SIC', 1474, 'Potash, Soda & Borate Minerals', 4, 2931),
(2933, 'SIC', 1475, 'Phosphate Rock', 4, 2931),
(2936, 'SIC', 1481, 'Nonmetallic Minerals Services', 4, 2935),
(2938, 'SIC', 1499, 'Miscellaneous Nonmetallic Minerals', 4, 2937),
(2942, 'SIC', 1522, 'Residential Construction, nec', 4, 2940),
(2941, 'SIC', 1521, 'Single-Family Housing Construction', 4, 2940),
(2232, 'SEC', 1531, 'Operative Builders', 4, 2231),
(2944, 'SIC', 1531, 'Operative Builders', 4, 2943),
(2946, 'SIC', 1541, 'Industrial Buildings & Warehouses', 4, 2945),
(2947, 'SIC', 1542, 'Nonresidential Construction, nec', 4, 2945),
(2950, 'SIC', 1611, 'Highway & Street Construction', 4, 2949),
(2236, 'SEC', 1623, 'Water, Sewer & Utility Lines', 4, 2235),
(2954, 'SIC', 1629, 'Heavy Construction, nec', 4, 2951),
(2953, 'SIC', 1623, 'Water, Sewer & Utility Lines', 4, 2951),
(2952, 'SIC', 1622, 'Bridge, Tunnel & Elevated Highway', 4, 2951),
(2957, 'SIC', 1711, 'Plumbing, Heating, Air-Conditioning', 4, 2956),
(2996, 'SIC', 2034, 'Dehydrated Fruits, Vegetables & Soups', 4, 2993),
(2995, 'SIC', 2033, 'Canned Fruits & Vegetables', 4, 2993),
(3005, 'SIC', 2046, 'Wet Corn Milling', 4, 3000),
(3007, 'SIC', 2048, 'Prepared Feeds, nec', 4, 3000),
(3006, 'SIC', 2047, 'Dog & Cat Food', 4, 3000),
(3004, 'SIC', 2045, 'Prepared Flour Mixes & Doughs', 4, 3000),
(3003, 'SIC', 2044, 'Rice Milling', 4, 3000),
(3002, 'SIC', 2043, 'Cereal Breakfast Foods', 4, 3000),
(3001, 'SIC', 2041, 'Flour & Other Grain Mill Products', 4, 3000),
(2251, 'SEC', 2052, 'Cookies & Crackers', 4, 2250),
(3009, 'SIC', 2051, 'Bread, Cake & Related Products', 4, 3008),
(3011, 'SIC', 2053, 'Frozen Bakery Products, Except Bread', 4, 3008),
(3010, 'SIC', 2052, 'Cookies & Crackers', 4, 3008),
(3015, 'SIC', 2063, 'Beet Sugar', 4, 3012),
(3019, 'SIC', 2068, 'Salted & Roasted Nuts & Seeds', 4, 3012),
(3018, 'SIC', 2067, 'Chewing Gum', 4, 3012),
(3017, 'SIC', 2066, 'Chocolate & Cocoa Products', 4, 3012),
(3016, 'SIC', 2064, 'Candy & Other Confectionery Products', 4, 3012),
(3072, 'SIC', 2273, 'Carpets & Rugs', 4, 3071),
(3075, 'SIC', 2282, 'Throwing & Winding Mills', 4, 3073),
(3076, 'SIC', 2284, 'Thread Mills', 4, 3073),
(3074, 'SIC', 2281, 'Yarn Spinning Mills', 4, 3073),
(3079, 'SIC', 2296, 'Tire Cord & Fabrics', 4, 3077),
(3082, 'SIC', 2299, 'Textile Goods, nec', 4, 3077),
(3081, 'SIC', 2298, 'Cordage & Twine', 4, 3077),
(3080, 'SIC', 2297, 'Nonwoven Fabrics', 4, 3077),
(3078, 'SIC', 2295, 'Coated Fabrics, Not Rubberized', 4, 3077),
(3085, 'SIC', 2311, 'Men''s & Boys'' Suits & Coats', 4, 3084),
(3087, 'SIC', 2321, 'Men''s & Boys'' Shirts', 4, 3086),
(3091, 'SIC', 2326, 'Men''s & Boys'' Work Clothing', 4, 3086),
(3092, 'SIC', 2329, 'Men''s & Boys'' Clothing, nec', 4, 3086),
(3088, 'SIC', 2322, 'Men''s & Boys'' Underwear & Nightwear', 4, 3086),
(3089, 'SIC', 2323, 'Men''s & Boys'' Neckwear', 4, 3086),
(3090, 'SIC', 2325, 'Men''s & Boys'' Trousers & Slacks', 4, 3086),
(3097, 'SIC', 2339, 'Women''s & Misses'' Outerwear, nec', 4, 3093),
(3094, 'SIC', 2331, 'Women''s & Misses'' Blouses & Shirts', 4, 3093),
(3095, 'SIC', 2335, 'Women''s & Misses'' & Junior''s Dresses', 4, 3093),
(3096, 'SIC', 2337, 'Women''s & Misses'' Suits & Coats', 4, 3093),
(3100, 'SIC', 2342, 'Bras, Girdles & Allied Garments', 4, 3098),
(3099, 'SIC', 2341, 'Women''s & Children''s Underwear', 4, 3098),
(3107, 'SIC', 2371, 'Fur Goods', 4, 3106),
(3147, 'SIC', 2499, 'Wood Products, nec', 4, 3144),
(3145, 'SIC', 2491, 'Wood Preserving', 4, 3144),
(3146, 'SIC', 2493, 'Reconstituted Wood Products', 4, 3144),
(2285, 'SEC', 2511, 'Wood Household Furniture', 4, 2284),
(3155, 'SIC', 2519, 'Household Furniture, nec', 4, 3149),
(3154, 'SIC', 2517, 'Wood TV & Radio Cabinets', 4, 3149),
(3153, 'SIC', 2515, 'Mattresses & Bedsprings', 4, 3149),
(3152, 'SIC', 2514, 'Metal Household Furniture', 4, 3149),
(3151, 'SIC', 2512, 'Upholstered Household Furniture', 4, 3149),
(3150, 'SIC', 2511, 'Wood Household Furniture', 4, 3149),
(2287, 'SEC', 2522, 'Office Furniture, Except Wood', 4, 2286),
(3158, 'SIC', 2522, 'Office Furniture, Except Wood', 4, 3156),
(3157, 'SIC', 2521, 'Wood Office Furniture', 4, 3156),
(2289, 'SEC', 2531, 'Public Building & Related Furniture', 4, 2288),
(3160, 'SIC', 2531, 'Public Building & Related Furniture', 4, 3159),
(3163, 'SIC', 2542, 'Partitions & Fixtures, Except Wood', 4, 3161),
(3165, 'SIC', 2591, 'Drapery Hardware & Blinds & Shades', 4, 3164),
(3166, 'SIC', 2599, 'Furniture & Fixtures, nec', 4, 3164),
(2294, 'SEC', 2611, 'Pulp Mills', 4, 2293),
(3169, 'SIC', 2611, 'Pulp Mills', 4, 3168),
(2296, 'SEC', 2621, 'Paper Mills', 4, 2295),
(3171, 'SIC', 2621, 'Paper Mills', 4, 3170),
(2298, 'SEC', 2631, 'Paperboard Mills', 4, 2297),
(3173, 'SIC', 2631, 'Paperboard Mills', 4, 3172),
(3175, 'SIC', 2652, 'Setup Paperboard Boxes', 4, 3174),
(3179, 'SIC', 2657, 'Folding Paperboard Boxes', 4, 3174),
(3177, 'SIC', 2655, 'Fiber Cans, Drums & Similar Products', 4, 3174),
(3176, 'SIC', 2653, 'Corrugated & Solid Fiber Boxes', 4, 3174),
(3178, 'SIC', 2656, 'Sanitary Food Containers', 4, 3174),
(2301, 'SEC', 2673, 'Bags: Plastic, Laminated & Coated', 4, 2300),
(3188, 'SIC', 2678, 'Stationery Products', 4, 3180),
(3189, 'SIC', 2679, 'Converted Paper Products, nec', 4, 3180),
(3183, 'SIC', 2673, 'Bags: Plastic, Laminated & Coated', 4, 3180),
(3184, 'SIC', 2674, 'Bags: Uncoated Paper & Multiwall', 4, 3180),
(3185, 'SIC', 2675, 'Die-Cut Paper & Board', 4, 3180),
(3186, 'SIC', 2676, 'Sanitary Paper Products', 4, 3180),
(3187, 'SIC', 2677, 'Envelopes', 4, 3180),
(3197, 'SIC', 2732, 'Book Printing', 4, 3195),
(3196, 'SIC', 2731, 'Book Publishing', 4, 3195),
(2311, 'SEC', 2741, 'Miscellaneous Publishing', 4, 2310),
(3199, 'SIC', 2741, 'Miscellaneous Publishing', 4, 3198),
(3202, 'SIC', 2754, 'Commercial Printing, Gravure', 4, 3200),
(3203, 'SIC', 2759, 'Commercial Printing, nec', 4, 3200),
(3201, 'SIC', 2752, 'Commercial Printing, Lithographic', 4, 3200),
(2314, 'SEC', 2761, 'Manifold Business Forms', 4, 2313),
(3205, 'SIC', 2761, 'Manifold Business Forms', 4, 3204),
(2316, 'SEC', 2771, 'Greeting Cards', 4, 2315),
(3207, 'SIC', 2771, 'Greeting Cards', 4, 3206),
(3209, 'SIC', 2782, 'Blankbooks & Looseleaf Binders', 4, 3208),
(3210, 'SIC', 2789, 'Bookbinding & Related Work', 4, 3208),
(3212, 'SIC', 2791, 'Typesetting', 4, 3211),
(3213, 'SIC', 2796, 'Platemaking Services', 4, 3211),
(3216, 'SIC', 2812, 'Alkalies & Chlorine', 4, 3215),
(3217, 'SIC', 2813, 'Industrial Gases', 4, 3215),
(3218, 'SIC', 2816, 'Inorganic Pigments', 4, 3215),
(3219, 'SIC', 2819, 'Industrial Inorganic Chemicals, nec', 4, 3215),
(2322, 'SEC', 2821, 'Plastics Materials & Resins', 4, 2321),
(3222, 'SIC', 2822, 'Synthetic Rubber', 4, 3220),
(3221, 'SIC', 2821, 'Plastics Materials & Resins', 4, 3220),
(3223, 'SIC', 2823, 'Cellulosic Manmade Fibers', 4, 3220),
(3248, 'SIC', 2892, 'Explosives', 4, 3246),
(3259, 'SIC', 2992, 'Lubricating Oils & Greases', 4, 3258),
(2344, 'SEC', 3011, 'Tires & Inner Tubes', 4, 2343),
(3263, 'SIC', 3011, 'Tires & Inner Tubes', 4, 3262),
(2346, 'SEC', 3021, 'Rubber & Plastics Footwear', 4, 2345),
(3265, 'SIC', 3021, 'Rubber & Plastics Footwear', 4, 3264),
(3267, 'SIC', 3052, 'Rubber & Plastics Hose & Belting', 4, 3266),
(3268, 'SIC', 3053, 'Gaskets, Packing & Sealing Devices', 4, 3266),
(3271, 'SIC', 3069, 'Fabricated Rubber Products, nec', 4, 3269),
(3270, 'SIC', 3061, 'Mechanical Rubber Goods', 4, 3269),
(2352, 'SEC', 3089, 'Plastics Products, nec', 4, 2349),
(2350, 'SEC', 3081, 'Unsupported Plastics Film & Sheet', 4, 2349),
(2351, 'SEC', 3086, 'Plastics Foam Products', 4, 2349),
(3276, 'SIC', 3084, 'Plastics Pipe', 4, 3272),
(3278, 'SIC', 3086, 'Plastics Foam Products', 4, 3272),
(3279, 'SIC', 3087, 'Custom Compound Purchased Resins', 4, 3272),
(3280, 'SIC', 3088, 'Plastics Plumbing Fixtures', 4, 3272),
(3281, 'SIC', 3089, 'Plastics Products, nec', 4, 3272),
(3273, 'SIC', 3081, 'Unsupported Plastics Film & Sheet', 4, 3272),
(3277, 'SIC', 3085, 'Plastics Bottles', 4, 3272),
(3274, 'SIC', 3082, 'Unsupported Plastics Profile Shapes', 4, 3272),
(3275, 'SIC', 3083, 'Laminated Plastics Plate, Sheet, and Profile Shapes', 4, 3272),
(3284, 'SIC', 3111, 'Leather Tanning & Finishing', 4, 3283),
(3286, 'SIC', 3131, 'Footwear Cut Stock', 4, 3285),
(3291, 'SIC', 3149, 'Footwear, Except Rubber, nec', 4, 3287),
(3289, 'SIC', 3143, 'Men''s Footwear, Except Athletic', 4, 3287),
(3290, 'SIC', 3144, 'Women''s Footwear, Except Athletic', 4, 3287),
(3288, 'SIC', 3142, 'House Slippers', 4, 3287),
(3293, 'SIC', 3151, 'Leather Gloves & Mittens', 4, 3292),
(3298, 'SIC', 3172, 'Personal Leather Goods, nec', 4, 3296),
(3297, 'SIC', 3171, 'Women''s Handbags & Purses', 4, 3296),
(3300, 'SIC', 3199, 'Leather Goods, nec', 4, 3299),
(2357, 'SEC', 3211, 'Flat Glass', 4, 2356),
(3303, 'SIC', 3211, 'Flat Glass', 4, 3302),
(2359, 'SEC', 3221, 'Glass Containers', 4, 2358),
(3305, 'SIC', 3221, 'Glass Containers', 4, 3304),
(3306, 'SIC', 3229, 'Pressed & Blown Glass, nec', 4, 3304),
(2361, 'SEC', 3231, 'Products of Purchased Glass', 4, 2360),
(3308, 'SIC', 3231, 'Products of Purchased Glass', 4, 3307),
(3321, 'SIC', 3269, 'Pottery Products, nec', 4, 3316),
(3319, 'SIC', 3263, 'Semivitreous Table & Kitchenware', 4, 3316),
(3317, 'SIC', 3261, 'Vitreous Plumbing Fixtures', 4, 3316),
(3318, 'SIC', 3262, 'Vitreous China Table & Kitchenware', 4, 3316),
(3320, 'SIC', 3264, 'Porcelain Electrical Supplies', 4, 3316),
(2367, 'SEC', 3272, 'Concrete Products, nec', 4, 2366),
(3325, 'SIC', 3273, 'Ready-Mixed Concrete', 4, 3322),
(3324, 'SIC', 3272, 'Concrete Products, nec', 4, 3322),
(3326, 'SIC', 3274, 'Lime', 4, 3322),
(3327, 'SIC', 3275, 'Gypsum Products', 4, 3322),
(3323, 'SIC', 3271, 'Concrete Block & Brick', 4, 3322),
(2369, 'SEC', 3281, 'Cut Stone & Stone Products', 4, 2368),
(3329, 'SIC', 3281, 'Cut Stone & Stone Products', 4, 3328),
(3336, 'SIC', 3299, 'Nonmetallic Mineral Products, nec', 4, 3330),
(3331, 'SIC', 3291, 'Abrasive Products', 4, 3330),
(3332, 'SIC', 3292, 'Asbestos Products', 4, 3330),
(3333, 'SIC', 3295, 'Minerals, Ground or Treated', 4, 3330),
(3334, 'SIC', 3296, 'Mineral Wool', 4, 3330),
(3335, 'SIC', 3297, 'Nonclay Refractories', 4, 3330),
(2373, 'SEC', 3312, 'Blast Furnaces & Steel Mills', 4, 2372),
(2374, 'SEC', 3317, 'Steel Pipe & Tubes', 4, 2372),
(3341, 'SIC', 3315, 'Steel Wire & Related Products', 4, 3338),
(3342, 'SIC', 3316, 'Cold Finishing of Steel Shapes', 4, 3338),
(3343, 'SIC', 3317, 'Steel Pipe & Tubes', 4, 3338),
(3339, 'SIC', 3312, 'Blast Furnaces & Steel Mills', 4, 3338),
(3340, 'SIC', 3313, 'Electrometallurgical Products', 4, 3338),
(3347, 'SIC', 3324, 'Steel Investment Foundries', 4, 3344),
(3348, 'SIC', 3325, 'Steel Foundries, nec', 4, 3344),
(3346, 'SIC', 3322, 'Malleable Iron Foundries', 4, 3344),
(3345, 'SIC', 3321, 'Gray & Ductile Iron Foundries', 4, 3344),
(2377, 'SEC', 3334, 'Primary Aluminum', 4, 2376),
(2387, 'SEC', 3412, 'Metal Barrels, Drums & Pails', 4, 2385),
(2386, 'SEC', 3411, 'Metal Cans', 4, 2385),
(3374, 'SIC', 3412, 'Metal Barrels, Drums & Pails', 4, 3372),
(3373, 'SIC', 3411, 'Metal Cans', 4, 3372),
(3377, 'SIC', 3423, 'Hand & Edge Tools, nec', 4, 3375),
(3379, 'SIC', 3429, 'Hardware, nec', 4, 3375),
(3378, 'SIC', 3425, 'Saw Blades & Handsaws', 4, 3375),
(3376, 'SIC', 3421, 'Cutlery', 4, 3375),
(2390, 'SEC', 3433, 'Heating Equipment, Except Electric', 4, 2389),
(3382, 'SIC', 3432, 'Plumbing Fixture Fittings & Trim', 4, 3380),
(3383, 'SIC', 3433, 'Heating Equipment, Except Electric', 4, 3380),
(3381, 'SIC', 3431, 'Metal Sanitary Ware', 4, 3380),
(2392, 'SEC', 3442, 'Metal Doors, Sash & Trim', 4, 2391),
(2393, 'SEC', 3443, 'Fabricated Plate Work (Boiler Shops)', 4, 2391),
(2395, 'SEC', 3448, 'Prefabricated Metal Buildings', 4, 2391),
(2394, 'SEC', 3444, 'Sheet Metal Work', 4, 2391),
(3391, 'SIC', 3449, 'Miscellaneous Metal Work', 4, 3384),
(3390, 'SIC', 3448, 'Prefabricated Metal Buildings', 4, 3384),
(3389, 'SIC', 3446, 'Architectural Metal Work', 4, 3384),
(3388, 'SIC', 3444, 'Sheet Metal Work', 4, 3384),
(3387, 'SIC', 3443, 'Fabricated Plate Work (Boiler Shops)', 4, 3384),
(3386, 'SIC', 3442, 'Metal Doors, Sash & Trim', 4, 3384),
(3432, 'SIC', 3536, 'Hoists, Cranes & Monorails', 4, 3426),
(3431, 'SIC', 3535, 'Conveyors & Conveying Equipment', 4, 3426),
(3430, 'SIC', 3534, 'Elevators & Moving Stairways', 4, 3426),
(3429, 'SIC', 3533, 'Oil & Gas Field Machinery', 4, 3426),
(3428, 'SIC', 3532, 'Mining Machinery', 4, 3426),
(2414, 'SEC', 3541, 'Machine Tools, Metal Cutting Types', 4, 2413),
(3443, 'SIC', 3549, 'Metalworking Machinery, nec', 4, 3434),
(3435, 'SIC', 3541, 'Machine Tools, Metal Cutting Types', 4, 3434),
(3436, 'SIC', 3542, 'Machine Tools, Metal Forming Types', 4, 3434),
(3437, 'SIC', 3543, 'Industrial Patterns', 4, 3434),
(3438, 'SIC', 3544, 'Special Dies, Tools, Jigs & Fixtures', 4, 3434),
(3439, 'SIC', 3545, 'Machine Tool Accessories', 4, 3434),
(3440, 'SIC', 3546, 'Power-Driven Handtools', 4, 3434),
(3441, 'SIC', 3547, 'Rolling Mill Machinery', 4, 3434),
(3442, 'SIC', 3548, 'Welding Apparatus', 4, 3434),
(2416, 'SEC', 3555, 'Printing Trades Machinery', 4, 2415),
(2417, 'SEC', 3559, 'Special Industry Machinery, nec', 4, 2415),
(3449, 'SIC', 3556, 'Food Products Machinery', 4, 3444),
(3483, 'SIC', 3613, 'Switchgear & Switchboard Apparatus', 4, 3481),
(3482, 'SIC', 3612, 'Transformers, Except Electronic', 4, 3481),
(2439, 'SEC', 3621, 'Motors & Generators', 4, 2438),
(3488, 'SIC', 3629, 'Electrical Industrial Apparatus, nec', 4, 3484),
(3486, 'SIC', 3624, 'Carbon & Graphite Products', 4, 3484),
(3485, 'SIC', 3621, 'Motors & Generators', 4, 3484),
(3487, 'SIC', 3625, 'Relays & Industrial Controls', 4, 3484),
(2441, 'SEC', 3634, 'Electric Housewares & Fans', 4, 2440),
(3490, 'SIC', 3631, 'Household Cooking Equipment', 4, 3489),
(3491, 'SIC', 3632, 'Household Refrigerators & Freezers', 4, 3489),
(3492, 'SIC', 3633, 'Household Laundry Equipment', 4, 3489),
(3493, 'SIC', 3634, 'Electric Housewares & Fans', 4, 3489),
(3494, 'SIC', 3635, 'Household Vacuum Cleaners', 4, 3489),
(3495, 'SIC', 3639, 'Household Appliances, nec', 4, 3489),
(3502, 'SIC', 3647, 'Vehicular Lighting Equipment', 4, 3496),
(3536, 'SIC', 3728, 'Aircraft Parts & Equipment, nec', 4, 3533),
(3535, 'SIC', 3724, 'Aircraft Engines & Engine Parts', 4, 3533),
(3539, 'SIC', 3732, 'Boat Building & Repairing', 4, 3537),
(3538, 'SIC', 3731, 'Ship Building & Repairing', 4, 3537),
(2471, 'SEC', 3743, 'Railroad Equipment', 4, 2470),
(3541, 'SIC', 3743, 'Railroad Equipment', 4, 3540),
(2473, 'SEC', 3751, 'Motorcycles, Bicycles & Parts', 4, 2472),
(3543, 'SIC', 3751, 'Motorcycles, Bicycles & Parts', 4, 3542),
(3546, 'SIC', 3764, 'Space Propulsion Units & Parts', 4, 3544),
(3547, 'SIC', 3769, 'Space Vehicle Equipment, nec', 4, 3544),
(3545, 'SIC', 3761, 'Guided Missiles & Space Vehicles', 4, 3544),
(3549, 'SIC', 3792, 'Travel Trailers & Campers', 4, 3548),
(3550, 'SIC', 3795, 'Tanks & Tank Components', 4, 3548),
(3551, 'SIC', 3799, 'Transportation Equipment, nec', 4, 3548),
(2478, 'SEC', 3812, 'Search & Navigation Equipment', 4, 2477),
(3554, 'SIC', 3812, 'Search & Navigation Equipment', 4, 3553),
(2482, 'SEC', 3823, 'Process Control Instruments', 4, 2479),
(2480, 'SEC', 3821, 'Laboratory Apparatus & Furniture', 4, 2479),
(2481, 'SEC', 3822, 'Environmental Controls', 4, 2479),
(2483, 'SEC', 3824, 'Fluid Meters & Counting Devices', 4, 2479),
(2484, 'SEC', 3825, 'Instruments to Measure Electricity', 4, 2479),
(2485, 'SEC', 3826, 'Analytical Instruments', 4, 2479),
(2486, 'SEC', 3827, 'Optical Instruments & Lenses', 4, 2479),
(2487, 'SEC', 3829, 'Measuring & Controlling Devices, nec', 4, 2479),
(2506, 'SEC', 3942, 'Dolls & Stuffed Toys', 4, 2505),
(2508, 'SEC', 3949, 'Sporting & Athletic Goods, nec', 4, 2505),
(2507, 'SEC', 3944, 'Games, Toys & Children''s Vehicles', 4, 2505),
(3586, 'SIC', 3949, 'Sporting & Athletic Goods, nec', 4, 3583),
(3584, 'SIC', 3942, 'Dolls & Stuffed Toys', 4, 3583),
(3585, 'SIC', 3944, 'Games, Toys & Children''s Vehicles', 4, 3583),
(3591, 'SIC', 3955, 'Carbon Paper & Inked Ribbons', 4, 3587),
(3590, 'SIC', 3953, 'Marking Devices', 4, 3587),
(3589, 'SIC', 3952, 'Lead Pencils & Art Goods', 4, 3587),
(3588, 'SIC', 3951, 'Pens & Mechanical Pencils', 4, 3587),
(3593, 'SIC', 3961, 'Costume Jewelry', 4, 3592),
(3594, 'SIC', 3965, 'Fasteners, Buttons, Needles & Pins', 4, 3592),
(3597, 'SIC', 3993, 'Signs & Advertising Specialties', 4, 3595),
(3600, 'SIC', 3999, 'Manufacturing Industries, nec', 4, 3595),
(3599, 'SIC', 3996, 'Hard Surface Floor Coverings, nec', 4, 3595),
(3598, 'SIC', 3995, 'Burial Caskets', 4, 3595),
(3596, 'SIC', 3991, 'Brooms & Brushes', 4, 3595),
(2514, 'SEC', 4011, 'Railroads Line-Haul Operating', 4, 2513),
(2515, 'SEC', 4013, 'Switching & Terminal Devices', 4, 2513),
(3604, 'SIC', 4013, 'Switching & Terminal Devices', 4, 3602),
(3603, 'SIC', 4011, 'Railroads Line-Haul Operating', 4, 3602),
(3608, 'SIC', 4119, 'Local Passenger Transportation, nec', 4, 3606),
(3607, 'SIC', 4111, 'Local & Suburban Transit', 4, 3606),
(3610, 'SIC', 4121, 'Taxicabs', 4, 3609),
(3612, 'SIC', 4131, 'Intercity & Rural Bus Transportation', 4, 3611),
(3615, 'SIC', 4142, 'Bus Charter Service, Except Local', 4, 3613),
(3614, 'SIC', 4141, 'Local Bus Charter Service', 4, 3613),
(3617, 'SIC', 4151, 'School Buses', 4, 3616),
(3619, 'SIC', 4173, 'Bus Terminal & Service Facilities', 4, 3618),
(2519, 'SEC', 4213, 'Trucking, Except Local', 4, 2518),
(3622, 'SIC', 4212, 'Local Trucking, Without Storage', 4, 3621),
(3624, 'SIC', 4214, 'Local Trucking With Storage', 4, 3621),
(3625, 'SIC', 4215, 'Courier Service, Except by Air', 4, 3621),
(3623, 'SIC', 4213, 'Trucking, Except Local', 4, 3621),
(3627, 'SIC', 4221, 'Farm Product Warehousing & Storage', 4, 3626),
(3630, 'SIC', 4226, 'Special Warehousing & Storage, nec', 4, 3626),
(3629, 'SIC', 4225, 'General Warehousing & Storage', 4, 3626),
(3628, 'SIC', 4222, 'Refrigerated Warehousing & Storage', 4, 3626),
(2522, 'SEC', 4231, 'Trucking Terminal Facilities', 4, 2521),
(2525, 'SEC', 4412, 'Deep Sea Foreign Transport of Freight', 4, 2524),
(3638, 'SIC', 4412, 'Deep Sea Foreign Transport of Freight', 4, 3637),
(3640, 'SIC', 4424, 'Deep Sea Domestic Transport of Freight', 4, 3639),
(3642, 'SIC', 4432, 'Freight Transport on The Great Lakes', 4, 3641),
(3644, 'SIC', 4449, 'Water Transportation of Freight, nec', 4, 3643),
(3648, 'SIC', 4489, 'Water Passenger Transportation, nec', 4, 3645),
(3646, 'SIC', 4481, 'Deep Sea Passenger Transportation, Except Ferry', 4, 3645),
(3647, 'SIC', 4482, 'Ferries', 4, 3645),
(3650, 'SIC', 4491, 'Marine Cargo Handling', 4, 3649),
(3653, 'SIC', 4499, 'Water Transportation Services, nec', 4, 3649),
(3652, 'SIC', 4493, 'Marinas', 4, 3649),
(3651, 'SIC', 4492, 'Towing & Tugboat Service', 4, 3649),
(2528, 'SEC', 4512, 'Air Transportation, Scheduled', 4, 2527),
(2529, 'SEC', 4513, 'Air Courier Services', 4, 2527),
(3656, 'SIC', 4512, 'Air Transportation, Scheduled', 4, 3655),
(3657, 'SIC', 4513, 'Air Courier Services', 4, 3655),
(2531, 'SEC', 4522, 'Air Transportation, Nonscheduled', 4, 2530),
(3659, 'SIC', 4522, 'Air Transportation, Nonscheduled', 4, 3658),
(2533, 'SEC', 4581, 'Airports, Flying Fields & Services', 4, 2532),
(3661, 'SIC', 4581, 'Airports, Flying Fields & Services', 4, 3660),
(3664, 'SIC', 4612, 'Crude Petroleum Pipelines', 4, 3663),
(3666, 'SIC', 4619, 'Pipelines, nec', 4, 3663),
(3665, 'SIC', 4613, 'Refined Petroleum Pipelines', 4, 3663),
(3670, 'SIC', 4725, 'Tour Operators', 4, 3668),
(3669, 'SIC', 4724, 'Travel Agencies', 4, 3668),
(3671, 'SIC', 4729, 'Passenger Transport Arrangement, nec', 4, 3668),
(2538, 'SEC', 4731, 'Freight Transportation Arrangement', 4, 2537),
(3673, 'SIC', 4731, 'Freight Transportation Arrangement', 4, 3672),
(3675, 'SIC', 4741, 'Rental of Railroad Cars', 4, 3674),
(3679, 'SIC', 4789, 'Transportation Services, nec', 4, 3676),
(3678, 'SIC', 4785, 'Inspection & Fixed Facilities', 4, 3676),
(3677, 'SIC', 4783, 'Packing & Crating', 4, 3676),
(2554, 'SEC', 4911, 'Electric Services', 4, 2553),
(3695, 'SIC', 4911, 'Electric Services', 4, 3694),
(2558, 'SEC', 4924, 'Natural Gas Distribution', 4, 2555),
(2556, 'SEC', 4922, 'Natural Gas Transmission', 4, 2555),
(2557, 'SEC', 4923, 'Gas Transmission & Distribution', 4, 2555),
(3698, 'SIC', 4923, 'Gas Transmission & Distribution', 4, 3696),
(3697, 'SIC', 4922, 'Natural Gas Transmission', 4, 3696),
(3700, 'SIC', 4925, 'Gas Production and/or Distribution', 4, 3696),
(3699, 'SIC', 4924, 'Natural Gas Distribution', 4, 3696),
(2561, 'SEC', 4932, 'Gas & Other Services Combined', 4, 2559),
(2560, 'SEC', 4931, 'Electric & Other Services Combined', 4, 2559),
(3704, 'SIC', 4939, 'Combination Utilities, nec', 4, 3701),
(3703, 'SIC', 4932, 'Gas & Other Services Combined', 4, 3701),
(3702, 'SIC', 4931, 'Electric & Other Services Combined', 4, 3701),
(2563, 'SEC', 4941, 'Water Supply', 4, 2562),
(3706, 'SIC', 4941, 'Water Supply', 4, 3705),
(2565, 'SEC', 4953, 'Refuse Systems', 4, 2564),
(3708, 'SIC', 4952, 'Sewerage Systems', 4, 3707),
(3709, 'SIC', 4953, 'Refuse Systems', 4, 3707),
(3710, 'SIC', 4959, 'Sanitary Services, nec', 4, 3707),
(2567, 'SEC', 4961, 'Steam & Air Conditioning Supply', 4, 2566),
(3712, 'SIC', 4961, 'Steam & Air Conditioning Supply', 4, 3711),
(3714, 'SIC', 4971, 'Irrigation Systems', 4, 3713),
(2570, 'SEC', 5013, 'Motor Vehicle Supplies & New Parts', 4, 2569),
(3719, 'SIC', 5014, 'Tires & Tubes', 4, 3716),
(3717, 'SIC', 5012, 'Automobiles & Other Motor Vehicles', 4, 3716),
(3718, 'SIC', 5013, 'Motor Vehicle Supplies & New Parts', 4, 3716),
(3720, 'SIC', 5015, 'Motor Vehicle Parts, Used', 4, 3716),
(3723, 'SIC', 5023, 'Homefurnishings', 4, 3721),
(3722, 'SIC', 5021, 'Furniture', 4, 3721),
(2573, 'SEC', 5031, 'Lumber, Plywood & Millwork', 4, 2572),
(3728, 'SIC', 5039, 'Construction Materials, nec', 4, 3724),
(3726, 'SIC', 5032, 'Brick, Stone & Related Materials', 4, 3724),
(2582, 'SEC', 5065, 'Electronic Parts & Equipment', 4, 2579),
(3743, 'SIC', 5065, 'Electronic Parts & Equipment', 4, 3740),
(3741, 'SIC', 5063, 'Electrical Apparatus & Equipment', 4, 3740),
(3742, 'SIC', 5064, 'Electrical Appliances, TV & Radios', 4, 3740),
(2584, 'SEC', 5072, 'Hardware', 4, 2583),
(3745, 'SIC', 5072, 'Hardware', 4, 3744),
(3747, 'SIC', 5075, 'Warm Air Heating & Air-Conditioning', 4, 3744),
(3746, 'SIC', 5074, 'Plumbing & Hydronic Heating Supplies', 4, 3744),
(3748, 'SIC', 5078, 'Refrigeration Equipment & Supplies', 4, 3744),
(2586, 'SEC', 5082, 'Construction & Mining Machinery', 4, 2585),
(2587, 'SEC', 5084, 'Industrial Machinery & Equipment', 4, 2585),
(3751, 'SIC', 5083, 'Farm & Garden Machinery', 4, 3749),
(3752, 'SIC', 5084, 'Industrial Machinery & Equipment', 4, 3749),
(3750, 'SIC', 5082, 'Construction & Mining Machinery', 4, 3749),
(3755, 'SIC', 5088, 'Transportation Equipment & Supplies', 4, 3749),
(3754, 'SIC', 5087, 'Service Establishment Equipment', 4, 3749),
(3753, 'SIC', 5085, 'Industrial Supplies', 4, 3749),
(2590, 'SEC', 5099, 'Durable Goods, nec', 4, 2588),
(2589, 'SEC', 5094, 'Jewelry & Precious Stones', 4, 2588),
(3761, 'SIC', 5099, 'Durable Goods, nec', 4, 3756),
(3843, 'SIC', 5531, 'Auto & Home Supply Stores', 4, 3842),
(3845, 'SIC', 5541, 'Gasoline Service Stations', 4, 3844),
(3847, 'SIC', 5551, 'Boat Dealers', 4, 3846),
(3849, 'SIC', 5561, 'Recreational Vehicle Dealers', 4, 3848),
(3851, 'SIC', 5571, 'Motorcycle Dealers', 4, 3850),
(3853, 'SIC', 5599, 'Automotive Dealers, nec', 4, 3852),
(3856, 'SIC', 5611, 'Men''s & Boys'' Clothing Stores', 4, 3855),
(2625, 'SEC', 5621, 'Women''s Clothing Stores', 4, 2624),
(3858, 'SIC', 5621, 'Women''s Clothing Stores', 4, 3857),
(3860, 'SIC', 5632, 'Women''s Accessory & Specialty Stores', 4, 3859),
(3862, 'SIC', 5641, 'Children''s & Infants'' Wear Stores', 4, 3861),
(2627, 'SEC', 5651, 'Family Clothing Stores', 4, 2626),
(3864, 'SIC', 5651, 'Family Clothing Stores', 4, 3863),
(2629, 'SEC', 5661, 'Shoe Stores', 4, 2628),
(3866, 'SIC', 5661, 'Shoe Stores', 4, 3865),
(3868, 'SIC', 5699, 'Miscellaneous Apparel & Accessory Stores', 4, 3867),
(2632, 'SEC', 5712, 'Furniture Stores', 4, 2631),
(3871, 'SIC', 5712, 'Furniture Stores', 4, 3870),
(3874, 'SIC', 5719, 'Miscellaneous Homefurnishings Stores', 4, 3870),
(3873, 'SIC', 5714, 'Drapery & Upholstery Stores', 4, 3870),
(3872, 'SIC', 5713, 'Floor Covering Stores', 4, 3870),
(3876, 'SIC', 5722, 'Household Appliance Stores', 4, 3875),
(2634, 'SEC', 5731, 'Radio, TV & Electronic Stores', 4, 2633),
(2636, 'SEC', 5735, 'Record & Prerecorded Tape Stores', 4, 2633),
(2635, 'SEC', 5734, 'Computer & Software Stores', 4, 2633),
(3880, 'SIC', 5735, 'Record & Prerecorded Tape Stores', 4, 3877),
(3878, 'SIC', 5731, 'Radio, TV & Electronic Stores', 4, 3877),
(3881, 'SIC', 5736, 'Musical Instrument Stores', 4, 3877),
(3879, 'SIC', 5734, 'Computer & Software Stores', 4, 3877),
(2639, 'SEC', 5812, 'Caterers & Banquet Halls', 4, 2638),
(3885, 'SIC', 5813, 'Drinking Places', 4, 3883),
(3884, 'SIC', 5812, 'Caterers & Banquet Halls', 4, 3883),
(2642, 'SEC', 5912, 'Drug Stores & Proprietary Stores', 4, 2641),
(3888, 'SIC', 5912, 'Drug Stores & Proprietary Stores', 4, 3887),
(3920, 'SIC', 6019, 'Central Reserve Depository, nec', 4, 3918),
(2651, 'SEC', 6021, 'National Commercial Banks', 4, 2650),
(2652, 'SEC', 6022, 'State Commercial Banks', 4, 2650),
(2653, 'SEC', 6029, 'Commercial Banks, nec', 4, 2650),
(3923, 'SIC', 6022, 'State Commercial Banks', 4, 3921),
(3922, 'SIC', 6021, 'National Commercial Banks', 4, 3921),
(3924, 'SIC', 6029, 'Commercial Banks, nec', 4, 3921),
(2656, 'SEC', 6036, 'Savings Institutions, Except Federal', 4, 2654),
(2655, 'SEC', 6035, 'Federal Savings Institutions', 4, 2654),
(3927, 'SIC', 6036, 'Savings Institutions, Except Federal', 4, 3925),
(3926, 'SIC', 6035, 'Federal Savings Institutions', 4, 3925),
(3930, 'SIC', 6062, 'State Credit Unions', 4, 3928),
(3929, 'SIC', 6061, 'Federal Credit Unions', 4, 3928),
(3932, 'SIC', 6081, 'Foreign Bank & Branches & Agencies', 4, 3931),
(3933, 'SIC', 6082, 'Foreign Trade & International Banks', 4, 3931),
(2658, 'SEC', 6099, 'Functions Related to Deposit Banking', 4, 2657),
(3936, 'SIC', 6099, 'Functions Related to Deposit Banking', 4, 3934),
(3935, 'SIC', 6091, 'Nondeposit Trust Facilities', 4, 3934),
(2661, 'SEC', 6111, 'Federal & Federally Sponsored Credit Agencies', 4, 2660),
(3939, 'SIC', 6111, 'Federal & Federally Sponsored Credit Agencies', 4, 3938),
(2663, 'SEC', 6141, 'Personal Credit Unions', 4, 2662),
(3941, 'SIC', 6141, 'Personal Credit Unions', 4, 3940),
(2665, 'SEC', 6153, 'Short Term Business Credit', 4, 2664),
(2666, 'SEC', 6159, 'Misc. Business Credit Institutions', 4, 2664),
(3944, 'SIC', 6159, 'Misc. Business Credit Institutions', 4, 3942),
(3943, 'SIC', 6153, 'Short Term Business Credit', 4, 3942),
(2669, 'SEC', 6163, 'Loan Brokers', 4, 2667),
(2668, 'SEC', 6162, 'Mortgage Bankers & Correspondents', 4, 2667),
(3946, 'SIC', 6162, 'Mortgage Bankers & Correspondents', 4, 3945),
(3947, 'SIC', 6163, 'Loan Brokers', 4, 3945),
(2672, 'SEC', 6211, 'Security Brokers & Dealers', 4, 2671),
(3950, 'SIC', 6211, 'Security Brokers & Dealers', 4, 3949),
(2674, 'SEC', 6221, 'Commodity Contracts Brokers, Dealers', 4, 2673),
(3952, 'SIC', 6221, 'Commodity Contracts Brokers, Dealers', 4, 3951),
(3954, 'SIC', 6231, 'Security & Commodity Exchanges', 4, 3953),
(2676, 'SEC', 6282, 'Investment Advice', 4, 2675),
(3957, 'SIC', 6289, 'Security & Commodity Services, nec', 4, 3955),
(3956, 'SIC', 6282, 'Investment Advice', 4, 3955),
(2679, 'SEC', 6311, 'Life Insurance', 4, 2678),
(3960, 'SIC', 6311, 'Life Insurance', 4, 3959),
(2682, 'SEC', 6324, 'Hospital & Medical Service Plans', 4, 2680),
(2681, 'SEC', 6321, 'Accident & Health Insurance', 4, 2680),
(3962, 'SIC', 6321, 'Accident & Health Insurance', 4, 3961),
(3963, 'SIC', 6324, 'Hospital & Medical Service Plans', 4, 3961),
(2684, 'SEC', 6331, 'Fire, Marine & Casualty Insurance', 4, 2683),
(3965, 'SIC', 6331, 'Fire, Marine & Casualty Insurance', 4, 3964),
(2686, 'SEC', 6351, 'Surety Insurance', 4, 2685),
(3967, 'SIC', 6351, 'Surety Insurance', 4, 3966),
(2688, 'SEC', 6361, 'Title Insurance', 4, 2687),
(3969, 'SIC', 6361, 'Title Insurance', 4, 3968),
(3971, 'SIC', 6371, 'Pension, Health & Welfare Funds', 4, 3970),
(2690, 'SEC', 6399, 'Insurance Carriers, nec', 4, 2689),
(3973, 'SIC', 6399, 'Insurance Carriers, nec', 4, 3972),
(2693, 'SEC', 6411, 'Insurance Agents, Brokers & Service', 4, 2692),
(3976, 'SIC', 6411, 'Insurance Agents, Brokers & Service', 4, 3975),
(2696, 'SEC', 6512, 'Nonresidential Building Operators', 4, 2695),
(2698, 'SEC', 6519, 'Real Property Lessors, nec', 4, 2695),
(2697, 'SEC', 6513, 'Apartment Building Operators', 4, 2695),
(3983, 'SIC', 6517, 'Railroad Property Lessors', 4, 3978),
(3984, 'SIC', 6519, 'Real Property Lessors, nec', 4, 3978),
(3979, 'SIC', 6512, 'Nonresidential Building Operators', 4, 3978),
(3980, 'SIC', 6513, 'Apartment Building Operators', 4, 3978),
(3981, 'SIC', 6514, 'Dwelling Operators, Except Apartments', 4, 3978),
(3982, 'SIC', 6515, 'Mobile Home Site Operators', 4, 3978),
(2700, 'SEC', 6531, 'Real Estate Agents & Managers', 4, 2699),
(3986, 'SIC', 6531, 'Real Estate Agents & Managers', 4, 3985),
(3988, 'SIC', 6541, 'Title Abstract Offices', 4, 3987),
(2702, 'SEC', 6552, 'Subdividers & Developers, nec', 4, 2701),
(3990, 'SIC', 6552, 'Subdividers & Developers, nec', 4, 3989),
(3991, 'SIC', 6553, 'Cemetery Subdividers & Developers', 4, 3989),
(3994, 'SIC', 6712, 'Bank Holding Companies', 4, 3993),
(3995, 'SIC', 6719, 'Holding Companies, nec', 4, 3993),
(4025, 'SIC', 7218, 'Industrial Launderers', 4, 4018),
(4026, 'SIC', 7219, 'Laundry & Garment Services, nec', 4, 4018),
(4019, 'SIC', 7211, 'Power Laundries, Family & Commercial', 4, 4018),
(4028, 'SIC', 7221, 'Photographic Studios, Portrait', 4, 4027),
(4030, 'SIC', 7231, 'Beauty Shops', 4, 4029),
(4032, 'SIC', 7241, 'Barber Shops', 4, 4031),
(4034, 'SIC', 7251, 'Shoe Repair & Shoeshine Parlors', 4, 4033),
(4036, 'SIC', 7261, 'Funeral Service & Crematories', 4, 4035),
(4039, 'SIC', 7299, 'Miscellaneous Personal Services, nec', 4, 4037),
(4038, 'SIC', 7291, 'Tax Return Preparation Services', 4, 4037),
(2715, 'SEC', 7311, 'Advertising Agencies', 4, 2714),
(4042, 'SIC', 7311, 'Advertising Agencies', 4, 4041),
(4044, 'SIC', 7313, 'Radio, TV Publisher Representatives', 4, 4041),
(4045, 'SIC', 7319, 'Advertising, nec', 4, 4041),
(4043, 'SIC', 7312, 'Outdoor Advertising Services', 4, 4041),
(4047, 'SIC', 7322, 'Adjustment & Collection Services', 4, 4046),
(4048, 'SIC', 7323, 'Credit Reporting Services', 4, 4046),
(2718, 'SEC', 7331, 'Direct Mail Advertising Services', 4, 2717),
(4050, 'SIC', 7331, 'Direct Mail Advertising Services', 4, 4049),
(4051, 'SIC', 7334, 'Photocopying & Duplicating Services', 4, 4049),
(4052, 'SIC', 7335, 'Commercial Photography', 4, 4049),
(4053, 'SIC', 7336, 'Commercial Art & Graphic Design', 4, 4049),
(4054, 'SIC', 7338, 'Secretarial & Court Reporting', 4, 4049),
(4057, 'SIC', 7349, 'Building Maintenance Services, nec', 4, 4055),
(4056, 'SIC', 7342, 'Disinfecting & Pest Control Services', 4, 4055),
(2721, 'SEC', 7359, 'Misc. Equipment Rental & Leasing, nec', 4, 2720),
(4061, 'SIC', 7359, 'Misc. Equipment Rental & Leasing, nec', 4, 4058),
(4059, 'SIC', 7352, 'Medical Equipment Rental', 4, 4058),
(4060, 'SIC', 7353, 'Heavy Construction Equipment Rental', 4, 4058),
(2723, 'SEC', 7361, 'Employment Agencies', 4, 2722),
(2724, 'SEC', 7363, 'Help Supply Services', 4, 2722),
(4063, 'SIC', 7361, 'Employment Agencies', 4, 4062),
(4064, 'SIC', 7363, 'Help Supply Services', 4, 4062),
(2727, 'SEC', 7372, 'Prepackaged Software', 4, 2725),
(2730, 'SEC', 7377, 'Computer Rental & Leasing', 4, 2725),
(2729, 'SEC', 7374, 'Data Processing & Preparation', 4, 2725),
(2728, 'SEC', 7373, 'Computer Integrated Systems Design', 4, 2725),
(2726, 'SEC', 7371, 'Computer Programming Services', 4, 2725),
(4071, 'SIC', 7376, 'Computer Facilities Management', 4, 4065),
(4069, 'SIC', 7374, 'Data Processing & Preparation', 4, 4065),
(4068, 'SIC', 7373, 'Computer Integrated Systems Design', 4, 4065),
(4119, 'SIC', 7829, 'Motion Picture Distribution Services', 4, 4117),
(4118, 'SIC', 7822, 'Motion Picture & Tape Distribution', 4, 4117),
(4121, 'SIC', 7832, 'Motion Picture Theaters, Except Drive-In', 4, 4120),
(4122, 'SIC', 7833, 'Drive-In Motion Picture Theaters', 4, 4120),
(2747, 'SEC', 7841, 'Video Tape Rental', 4, 2746),
(4124, 'SIC', 7841, 'Video Tape Rental', 4, 4123),
(4127, 'SIC', 7911, 'Dance Studios, Schools & Halls', 4, 4126),
(4129, 'SIC', 7922, 'Theatrical Producers & Services', 4, 4128),
(4130, 'SIC', 7929, 'Entertainers & Entertainment Groups', 4, 4128),
(4132, 'SIC', 7933, 'Bowling Centers', 4, 4131),
(2750, 'SEC', 7948, 'Racing, Including Track Operation', 4, 2749),
(4134, 'SIC', 7941, 'Sports Clubs, Managers & Promoters', 4, 4133),
(4135, 'SIC', 7948, 'Racing, Including Track Operation', 4, 4133),
(4137, 'SIC', 7951, 'Ski Facilities, Down Hill', 4, 4136),
(4138, 'SIC', 7952, 'Ski Facilities, Cross Country', 4, 4136),
(2752, 'SEC', 7997, 'Membership Sports & Recreation Clubs', 4, 2751),
(4140, 'SIC', 7991, 'Physical Fitness Facilities', 4, 4139),
(4145, 'SIC', 7999, 'Amusement & Recreation, nec', 4, 4139),
(4144, 'SIC', 7997, 'Membership Sports & Recreation Clubs', 4, 4139),
(4143, 'SIC', 7996, 'Amusement Parks', 4, 4139),
(4142, 'SIC', 7993, 'Coin-Operated Amusement Devices', 4, 4139),
(4141, 'SIC', 7992, 'Public Golf Courses', 4, 4139),
(2755, 'SEC', 8011, 'Offices & Clinics of Medical Doctors', 4, 2754),
(4148, 'SIC', 8011, 'Offices & Clinics of Medical Doctors', 4, 4147),
(4150, 'SIC', 8021, 'Offices & Clinics of Dentists', 4, 4149),
(4152, 'SIC', 8031, 'Offices of Osteopathic Physicians', 4, 4151),
(4157, 'SIC', 8049, 'Offices of Health Practitioners, nec', 4, 4153),
(4156, 'SIC', 8043, 'Offices & Clinics of Podiatrists', 4, 4153),
(4180, 'SIC', 8211, 'Elementary & Secondary Schools', 4, 4179),
(4182, 'SIC', 8221, 'Colleges & Universities', 4, 4181),
(4183, 'SIC', 8222, 'Junior Colleges', 4, 4181),
(4185, 'SIC', 8231, 'Libraries', 4, 4184),
(4187, 'SIC', 8243, 'Data Processing Schools', 4, 4186),
(4189, 'SIC', 8249, 'Vocational Schools, nec', 4, 4186),
(4188, 'SIC', 8244, 'Business & Secretarial Schools', 4, 4186),
(4191, 'SIC', 8299, 'Schools & Educational Services, nec', 4, 4190),
(4194, 'SIC', 8322, 'Individual & Family Services', 4, 4193),
(4196, 'SIC', 8331, 'Job Training & Related Services', 4, 4195),
(2772, 'SEC', 8351, 'Child Day Care Services', 4, 2771),
(4198, 'SIC', 8351, 'Child Day Care Services', 4, 4197),
(4200, 'SIC', 8361, 'Residential Care', 4, 4199),
(4202, 'SIC', 8399, 'Social Services, nec', 4, 4201),
(4205, 'SIC', 8412, 'Museums & Art Galleries', 4, 4204),
(4207, 'SIC', 8422, 'Botanical & Zoological Gardens', 4, 4206),
(4210, 'SIC', 8611, 'Business Associations', 4, 4209),
(4212, 'SIC', 8621, 'Professional Organizations', 4, 4211),
(4214, 'SIC', 8631, 'Labor Organizations', 4, 4213),
(4216, 'SIC', 8641, 'Civic & Social Organizations', 4, 4215),
(4218, 'SIC', 8651, 'Political Organizations', 4, 4217),
(4220, 'SIC', 8661, 'Religious Organizations', 4, 4219),
(4222, 'SIC', 8699, 'Membership Organizations, nec', 4, 4221),
(2776, 'SEC', 8711, 'Engineering Services', 4, 2775),
(4226, 'SIC', 8712, 'Architectural Services', 4, 4224),
(4227, 'SIC', 8713, 'Surveying Services', 4, 4224),
(4225, 'SIC', 8711, 'Engineering Services', 4, 4224),
(4229, 'SIC', 8721, 'Accounting, Auditing & Bookkeeping', 4, 4228),
(2778, 'SEC', 8731, 'Commercial Physical Research', 4, 2777),
(2779, 'SEC', 8734, 'Testing Laboratories', 4, 2777),
(4232, 'SIC', 8732, 'Commercial Nonphysical Research', 4, 4230),
(4234, 'SIC', 8734, 'Testing Laboratories', 4, 4230),
(4231, 'SIC', 8731, 'Commercial Physical Research', 4, 4230),
(4233, 'SIC', 8733, 'Noncommercial Research Organizations', 4, 4230),
(2781, 'SEC', 8741, 'Management Services', 4, 2780),
(2783, 'SEC', 8744, 'Facilities Support Services', 4, 2780),
(2782, 'SEC', 8742, 'Management Consulting Services', 4, 2780),
(4249, 'SIC', 9111, 'Executive Offices', 4, 4248),
(4251, 'SIC', 9121, 'Legislative Bodies', 4, 4250),
(4253, 'SIC', 9131, 'Executive & Legislative Combined', 4, 4252),
(4255, 'SIC', 9191, 'General Government, nec', 4, 4254),
(4258, 'SIC', 9211, 'Courts', 4, 4257),
(4261, 'SIC', 9222, 'Legal Counsel & Prosecution', 4, 4259),
(4262, 'SIC', 9223, 'Correctional Institutions', 4, 4259),
(4263, 'SIC', 9224, 'Fire Protection', 4, 4259),
(4264, 'SIC', 9229, 'Public Order & Safety, nec', 4, 4259),
(4260, 'SIC', 9221, 'Police Protection', 4, 4259),
(4267, 'SIC', 9311, 'Finance, Taxation & Monetary Policy', 4, 4266),
(4270, 'SIC', 9411, 'Admin. of Educational Programs', 4, 4269),
(4272, 'SIC', 9431, 'Admin. of Public Health Programs', 4, 4271),
(4274, 'SIC', 9441, 'Admin. of Social & Manpower Programs', 4, 4273),
(4276, 'SIC', 9451, 'Administration of Veteran''s Affairs', 4, 4275),
(4280, 'SIC', 9512, 'Land, Mineral, Wildlife Conservation', 4, 4278),
(4279, 'SIC', 9511, 'Air, Water & Solid Waste Management', 4, 4278),
(4283, 'SIC', 9532, 'Urban & Community Development', 4, 4281),
(4282, 'SIC', 9531, 'Housing Programs', 4, 4281),
(4286, 'SIC', 9611, 'Administration of General Economic Programs', 4, 4285),
(4288, 'SIC', 9621, 'Regulation, Admin. of Transportation', 4, 4287),
(4290, 'SIC', 9631, 'Regulation, Admin. of Utilities', 4, 4289),
(1321, 'NAICS', 4855, 'Charter Bus Industry', 3, 1303),
(2163, 'NAICS', 92216, 'Fire Protection', 4, 2151),
(3127, 'SIC', 2420, 'Sawmills & Planing Mills', 3, 3124),
(3840, 'SIC', 5520, 'Used Car Dealers', 3, 3837),
(2210, 'SEC', 100, 'AGRICULTURAL PRODUCTION - CROPS', 2, 2788),
(2212, 'SEC', 700, 'AGRICULTURAL SERVICES', 2, 2788),
(2211, 'SEC', 200, 'AGRICULTURAL PRODUCTION - LIVESTOCK', 2, 2788),
(2875, 'SIC', 900, 'FISHING, HUNTING & TRAPPING', 2, 4305),
(2798, 'SIC', 100, 'AGRICULTURAL PRODUCTION - CROPS', 2, 4305),
(2825, 'SIC', 200, 'AGRICULTURAL PRODUCTION - LIVESTOCK', 2, 4305),
(2847, 'SIC', 700, 'AGRICULTURAL SERVICES', 2, 4305),
(2820, 'SIC', 180, 'Horticultural Specialties', 3, 2798),
(2805, 'SIC', 130, 'Field Crops, Except Cash Grains', 3, 2798),
(2811, 'SIC', 160, 'Vegetables & Melons', 3, 2798),
(2823, 'SIC', 190, 'General Farms, Primarily Crop', 3, 2798),
(2813, 'SIC', 170, 'Fruits & Tree Nuts', 3, 2798),
(2897, 'SIC', 1081, 'Metal Mining Services', 4, 2896),
(2899, 'SIC', 1094, 'Uranium Radium Vanadium Ores', 4, 2898),
(2220, 'SEC', 1221, 'Bituminous Coal & Lignite - Surface', 4, 2219),
(2903, 'SIC', 1221, 'Bituminous Coal & Lignite - Surface', 4, 2902),
(2904, 'SIC', 1222, 'Bituminous Coal - Underground', 4, 2902),
(2906, 'SIC', 1231, 'Anthracite Mining', 4, 2905),
(2908, 'SIC', 1241, 'Coal Mining Services', 4, 2907),
(2218, 'SEC', 1200, 'COAL MINING', 2, 2789),
(2959, 'SIC', 1721, 'Painting & Paper Hanging', 4, 2958),
(2239, 'SEC', 1731, 'Electrical Work', 4, 2238),
(2961, 'SIC', 1731, 'Electrical Work', 4, 2960),
(2965, 'SIC', 1743, 'Terrazzo, Tile, Marble, Mosaic Work', 4, 2962),
(2964, 'SIC', 1742, 'Plastering, Drywall & Insulation', 4, 2962),
(2963, 'SIC', 1741, 'Masonry & Other Stonework', 4, 2962),
(2968, 'SIC', 1752, 'Floor Laying & Floor Work, nec', 4, 2966),
(2967, 'SIC', 1751, 'Carpentry Work', 4, 2966),
(2970, 'SIC', 1761, 'Roofing, Siding & Sheet Metal Work', 4, 2969),
(2972, 'SIC', 1771, 'Concrete Work', 4, 2971),
(2974, 'SIC', 1781, 'Water Well Drilling', 4, 2973),
(2977, 'SIC', 1793, 'Glass & Glazing Work', 4, 2975),
(3013, 'SIC', 2061, 'Raw Cane Sugar', 4, 3012),
(3014, 'SIC', 2062, 'Cane Sugar Refining', 4, 3012),
(3021, 'SIC', 2074, 'Cottonseed Oil Mills', 4, 3020),
(3025, 'SIC', 2079, 'Edible Fats & Oils, nec', 4, 3020),
(3024, 'SIC', 2077, 'Animal & Marine Fats & Oils', 4, 3020),
(3023, 'SIC', 2076, 'Vegetable Oil Mills, nec', 4, 3020),
(3022, 'SIC', 2075, 'Soybean Oil Mills', 4, 3020),
(2256, 'SEC', 2086, 'Bottled & Canned Soft Drinks', 4, 2254),
(2255, 'SEC', 2082, 'Malt Beverages', 4, 2254),
(3029, 'SIC', 2084, 'Wines, Brandy & Brandy Spirits', 4, 3026),
(3028, 'SIC', 2083, 'Malt', 4, 3026),
(3027, 'SIC', 2082, 'Malt Beverages', 4, 3026),
(3031, 'SIC', 2086, 'Bottled & Canned Soft Drinks', 4, 3026),
(3030, 'SIC', 2085, 'Distilled & Blended Liquors', 4, 3026),
(3032, 'SIC', 2087, 'Flavoring Extracts & Syrups, nec', 4, 3026),
(2258, 'SEC', 2092, 'Fresh or Frozen Prepared Fish', 4, 2257),
(3034, 'SIC', 2091, 'Canned & Cured Fish & Seafoods', 4, 3033),
(3039, 'SIC', 2098, 'Macaroni & Spaghetti', 4, 3033),
(3038, 'SIC', 2097, 'Manufactured Ice', 4, 3033),
(3037, 'SIC', 2096, 'Potato Chips & Similar Snacks', 4, 3033),
(3035, 'SIC', 2092, 'Fresh or Frozen Prepared Fish', 4, 3033),
(3036, 'SIC', 2095, 'Roasted Coffee', 4, 3033),
(2261, 'SEC', 2111, 'Cigarettes', 4, 2260),
(3043, 'SIC', 2111, 'Cigarettes', 4, 3042),
(3045, 'SIC', 2121, 'Cigars', 4, 3044),
(3047, 'SIC', 2131, 'Chewing & Smoking Tobacco', 4, 3046),
(3049, 'SIC', 2141, 'Tobacco Stemming & Redrying', 4, 3048),
(2264, 'SEC', 2211, 'Broadwoven Fabric Mills, Cotton', 4, 2263),
(3052, 'SIC', 2211, 'Broadwoven Fabric Mills, Cotton', 4, 3051),
(2266, 'SEC', 2221, 'Broadwoven Fabric Mills, Manmade', 4, 2265),
(3054, 'SIC', 2221, 'Broadwoven Fabric Mills, Manmade', 4, 3053),
(3056, 'SIC', 2231, 'Broadwoven Fabric Mills, Wool', 4, 3055),
(3058, 'SIC', 2241, 'Narrow Fabric Mills', 4, 3057),
(2268, 'SEC', 2253, 'Knit Outerwear Mills', 4, 2267),
(3062, 'SIC', 2253, 'Knit Outerwear Mills', 4, 3059),
(3066, 'SIC', 2259, 'Knitting Mills, nec', 4, 3059),
(3065, 'SIC', 2258, 'Lace & Warp Knit Fabric Mills', 4, 3059),
(3064, 'SIC', 2257, 'Weft Knit Fabric Mills', 4, 3059),
(3063, 'SIC', 2254, 'Knit Underwear Mills', 4, 3059),
(3061, 'SIC', 2252, 'Hosiery, nec', 4, 3059),
(3060, 'SIC', 2251, 'Women''s Hosiery, Except Socks', 4, 3059),
(3068, 'SIC', 2261, 'Finishing Plants, Cotton', 4, 3067),
(3069, 'SIC', 2262, 'Finishing Plants, Manmade', 4, 3067),
(3070, 'SIC', 2269, 'Finishing Plants, nec', 4, 3067),
(2270, 'SEC', 2273, 'Carpets & Rugs', 4, 2269),
(2260, 'SEC', 2110, 'Cigarettes', 3, 2259),
(3102, 'SIC', 2353, 'Hats, Caps & Millinery', 4, 3101),
(3104, 'SIC', 2361, 'Girls & Children''s Dresses & Blouses', 4, 3103),
(3105, 'SIC', 2369, 'Girls & Children''s Outerwear, nec', 4, 3103),
(3109, 'SIC', 2381, 'Fabric Dress & Work Gloves', 4, 3108),
(3113, 'SIC', 2387, 'Apparel Belts', 4, 3108),
(3114, 'SIC', 2389, 'Apparel & Accessories, nec', 4, 3108),
(3112, 'SIC', 2386, 'Leather & Sheep-Lined Clothing', 4, 3108),
(3111, 'SIC', 2385, 'Waterproof Outerwear', 4, 3108),
(3110, 'SIC', 2384, 'Robes & Dressing Gowns', 4, 3108),
(3120, 'SIC', 2395, 'Pleating & Stitching', 4, 3115),
(3122, 'SIC', 2397, 'Schiffli Machine Embroideries', 4, 3115),
(3116, 'SIC', 2391, 'Curtains & Draperies', 4, 3115),
(3123, 'SIC', 2399, 'Fabricated Textile Products, nec', 4, 3115),
(3117, 'SIC', 2392, 'House Furnishings, nec', 4, 3115),
(3118, 'SIC', 2393, 'Textile Bags', 4, 3115),
(3119, 'SIC', 2394, 'Canvas & Related Products', 4, 3115),
(3121, 'SIC', 2396, 'Automotive & Apparel Trimmings', 4, 3115),
(3126, 'SIC', 2411, 'Logging', 4, 3125),
(2278, 'SEC', 2421, 'Sawmills & Planing Mills, General', 4, 2277),
(3128, 'SIC', 2421, 'Sawmills & Planing Mills, General', 4, 3127),
(3130, 'SIC', 2429, 'Special Product Sawmills, nec', 4, 3127),
(3129, 'SIC', 2426, 'Hardwood Dimension & Flooring Mills', 4, 3127),
(3134, 'SIC', 2435, 'Hardwood Veneer & Plywood', 4, 3131),
(3133, 'SIC', 2434, 'Wood Kitchen Cabinets', 4, 3131),
(3132, 'SIC', 2431, 'Millwork', 4, 3131),
(3136, 'SIC', 2439, 'Structural Wood Members, nec', 4, 3131),
(3135, 'SIC', 2436, 'Softwood Veneer & Plywood', 4, 3131),
(3139, 'SIC', 2448, 'Wood Pallets & Skids', 4, 3137),
(3138, 'SIC', 2441, 'Nailed Wood Boxes & Shook', 4, 3137),
(3140, 'SIC', 2449, 'Wood Containers, nec', 4, 3137),
(2281, 'SEC', 2451, 'Mobile Homes', 4, 2280),
(2282, 'SEC', 2452, 'Prefabricated Wood Buildings', 4, 2280),
(3142, 'SIC', 2451, 'Mobile Homes', 4, 3141),
(3143, 'SIC', 2452, 'Prefabricated Wood Buildings', 4, 3141),
(3106, 'SIC', 2370, 'Fur Goods', 3, 3083),
(3181, 'SIC', 2671, 'Paper Coated & Laminated, Packaging', 4, 3180),
(3182, 'SIC', 2672, 'Paper Coated & Laminated, nec', 4, 3180),
(2304, 'SEC', 2711, 'Newspapers', 4, 2303),
(3192, 'SIC', 2711, 'Newspapers', 4, 3191),
(2306, 'SEC', 2721, 'Periodicals', 4, 2305),
(3194, 'SIC', 2721, 'Periodicals', 4, 3193),
(2309, 'SEC', 2732, 'Book Printing', 4, 2307),
(2308, 'SEC', 2731, 'Book Publishing', 4, 2307),
(3224, 'SIC', 2824, 'Organic Fibers, Noncellulosic', 4, 3220),
(2326, 'SEC', 2835, 'Diagnostic Substances', 4, 2323),
(2327, 'SEC', 2836, 'Biological Products, Except Diagnostic', 4, 2323),
(2324, 'SEC', 2833, 'Medicinals & Botanicals', 4, 2323),
(2325, 'SEC', 2834, 'Pharmaceutical Preparations', 4, 2323),
(3229, 'SIC', 2836, 'Biological Products, Except Diagnostic', 4, 3225),
(3226, 'SIC', 2833, 'Medicinals & Botanicals', 4, 3225),
(3228, 'SIC', 2835, 'Diagnostic Substances', 4, 3225),
(3227, 'SIC', 2834, 'Pharmaceutical Preparations', 4, 3225),
(2329, 'SEC', 2842, 'Polishes & Sanitation Goods', 4, 2328),
(2330, 'SEC', 2844, 'Perfumes & Cosmetics -Toilet Preparations', 4, 2328),
(3231, 'SIC', 2841, 'Soap & Other Detergents', 4, 3230),
(3232, 'SIC', 2842, 'Polishes & Sanitation Goods', 4, 3230),
(3233, 'SIC', 2843, 'Surface Active Agents', 4, 3230),
(3234, 'SIC', 2844, 'Perfumes & Cosmetics -Toilet Preparations', 4, 3230),
(2332, 'SEC', 2851, 'Paints & Allied Products', 4, 2331),
(3236, 'SIC', 2851, 'Paints & Allied Products', 4, 3235),
(3240, 'SIC', 2869, 'Industrial Organic Chemicals, nec', 4, 3237),
(3238, 'SIC', 2861, 'Gum & Wood Chemicals', 4, 3237),
(3239, 'SIC', 2865, 'Cyclic Crudes & Intermediates', 4, 3237),
(3244, 'SIC', 2875, 'Fertilizers, Mixing Only', 4, 3241),
(3245, 'SIC', 2879, 'Agricultural Chemicals, nec', 4, 3241),
(3243, 'SIC', 2874, 'Phosphatic Fertilizers', 4, 3241),
(3242, 'SIC', 2873, 'Nitrogenous Fertilizers', 4, 3241),
(2336, 'SEC', 2891, 'Adhesives & Sealants', 4, 2335),
(3251, 'SIC', 2899, 'Chemical Preparations, nec', 4, 3246),
(3247, 'SIC', 2891, 'Adhesives & Sealants', 4, 3246),
(3249, 'SIC', 2893, 'Printing Ink', 4, 3246),
(3250, 'SIC', 2895, 'Carbon Black', 4, 3246),
(2339, 'SEC', 2911, 'Petroleum Refining', 4, 2338),
(3254, 'SIC', 2911, 'Petroleum Refining', 4, 3253),
(3256, 'SIC', 2951, 'Asphalt Paving Mixtures & Blocks', 4, 3255),
(3257, 'SIC', 2952, 'Asphalt Felts & Coatings', 4, 3255),
(3260, 'SIC', 2999, 'Petroleum & Coal Products, nec', 4, 3258),
(2363, 'SEC', 3241, 'Cement, Hydraulic', 4, 2362),
(3310, 'SIC', 3241, 'Cement, Hydraulic', 4, 3309),
(3313, 'SIC', 3253, 'Ceramic Wall & Floor Tile', 4, 3311),
(3314, 'SIC', 3255, 'Clay Refectories', 4, 3311),
(3315, 'SIC', 3259, 'Structural Clay Products, nec', 4, 3311),
(3312, 'SIC', 3251, 'Brick & Structural Clay Tile', 4, 3311),
(3351, 'SIC', 3334, 'Primary Aluminum', 4, 3349),
(3352, 'SIC', 3339, 'Primary Nonferrous Metals, nec', 4, 3349),
(3350, 'SIC', 3331, 'Primary Copper', 4, 3349),
(2379, 'SEC', 3341, 'Secondary Nonferrous Metals', 4, 2378),
(3354, 'SIC', 3341, 'Secondary Nonferrous Metals', 4, 3353),
(2381, 'SEC', 3357, 'Nonferrous Wiredrawing & Insulating', 4, 2380),
(3357, 'SIC', 3353, 'Aluminum Sheet, Plate & Foil', 4, 3355),
(3359, 'SIC', 3355, 'Aluminum Rolling & Drawing, nec', 4, 3355),
(3361, 'SIC', 3357, 'Nonferrous Wiredrawing & Insulating', 4, 3355),
(3360, 'SIC', 3356, 'Nonferrous Rolling & Drawing, nec', 4, 3355),
(3356, 'SIC', 3351, 'Copper Rolling & Drawing', 4, 3355),
(3358, 'SIC', 3354, 'Aluminum Extruded Products', 4, 3355),
(3365, 'SIC', 3365, 'Aluminum Foundries', 4, 3362),
(3367, 'SIC', 3369, 'Nonferrous Foundries, nec', 4, 3362),
(3364, 'SIC', 3364, 'Nonferrous Die Castings, Except Aluminum', 4, 3362),
(3366, 'SIC', 3366, 'Copper Foundries', 4, 3362),
(3363, 'SIC', 3363, 'Aluminum Die Castings', 4, 3362),
(3370, 'SIC', 3399, 'Primary Metal Products, nec', 4, 3368),
(3369, 'SIC', 3398, 'Metal Heat Treating', 4, 3368),
(2400, 'SEC', 3470, 'Metal Services, nec', 3, 2384),
(3385, 'SIC', 3441, 'Fabricated Structural Metal', 4, 3384),
(2398, 'SEC', 3452, 'Bolts, Nuts, Rivets & Washers', 4, 2396),
(2397, 'SEC', 3451, 'Screw Machine Products', 4, 2396),
(3394, 'SIC', 3452, 'Bolts, Nuts, Rivets & Washers', 4, 3392),
(3393, 'SIC', 3451, 'Screw Machine Products', 4, 3392),
(3399, 'SIC', 3466, 'Crowns & Closures', 4, 3395),
(3400, 'SIC', 3469, 'Metal Stampings, nec', 4, 3395),
(3396, 'SIC', 3462, 'Iron & Steel Forgings', 4, 3395),
(3397, 'SIC', 3463, 'Nonferrous Forgings', 4, 3395),
(3398, 'SIC', 3465, 'Automotive Stampings', 4, 3395),
(3402, 'SIC', 3471, 'Plating & Polishing', 4, 3401),
(3403, 'SIC', 3479, 'Metal Coating & Allied Services', 4, 3401),
(3406, 'SIC', 3483, 'Ammunition, Except for Small Arms, nec', 4, 3404),
(3405, 'SIC', 3482, 'Small Arms Ammunition', 4, 3404),
(3408, 'SIC', 3489, 'Ordnance & Accessories, nec', 4, 3404),
(3407, 'SIC', 3484, 'Small Arms', 4, 3404),
(3412, 'SIC', 3493, 'Steel Spring, Except Wire', 4, 3409),
(3418, 'SIC', 3499, 'Fabricated Metal Products, nec', 4, 3409),
(3417, 'SIC', 3498, 'Fabricated Pipe & Fittings', 4, 3409),
(3416, 'SIC', 3497, 'Metal Foil & Leaf', 4, 3409),
(3415, 'SIC', 3496, 'Miscellaneous Fabricated Wire Products', 4, 3409),
(3414, 'SIC', 3495, 'Wire Springs', 4, 3409),
(3413, 'SIC', 3494, 'Valves & Pipe Fittings, nec', 4, 3409),
(3411, 'SIC', 3492, 'Fluid Power Valves & Hose Fittings', 4, 3409),
(3410, 'SIC', 3491, 'Industrial Valves', 4, 3409),
(3422, 'SIC', 3519, 'Internal Combustion Engines, nec', 4, 3420),
(3421, 'SIC', 3511, 'Turbines & Turbine Generator Sets', 4, 3420),
(2407, 'SEC', 3524, 'Lawn & Garden Equipment', 4, 2405),
(2406, 'SEC', 3523, 'Farm Machinery & Equipment', 4, 2405),
(3425, 'SIC', 3524, 'Lawn & Garden Equipment', 4, 3423),
(3424, 'SIC', 3523, 'Farm Machinery & Equipment', 4, 3423),
(2412, 'SEC', 3537, 'Industrial Trucks & Tractors', 4, 2408),
(2409, 'SEC', 3531, 'Construction Machinery', 4, 2408),
(2410, 'SEC', 3532, 'Mining Machinery', 4, 2408),
(2411, 'SEC', 3533, 'Oil & Gas Field Machinery', 4, 2408),
(3427, 'SIC', 3531, 'Construction Machinery', 4, 3426),
(3433, 'SIC', 3537, 'Industrial Trucks & Tractors', 4, 3426),
(3450, 'SIC', 3559, 'Special Industry Machinery, nec', 4, 3444),
(3445, 'SIC', 3552, 'Textile Machinery', 4, 3444),
(3447, 'SIC', 3554, 'Paper Industries Machinery', 4, 3444),
(3446, 'SIC', 3553, 'Woodworking Machinery', 4, 3444),
(3448, 'SIC', 3555, 'Printing Trades Machinery', 4, 3444),
(2420, 'SEC', 3562, 'Ball & Roller Bearings', 4, 2418),
(2421, 'SEC', 3564, 'Blowers & Fans', 4, 2418),
(2422, 'SEC', 3567, 'Industrial Furnaces & Ovens', 4, 2418),
(2423, 'SEC', 3569, 'General Industrial Machinery, nec', 4, 2418),
(2419, 'SEC', 3561, 'Pumps & Pumping Equipment', 4, 2418),
(3452, 'SIC', 3561, 'Pumps & Pumping Equipment', 4, 3451),
(3454, 'SIC', 3563, 'Air & Gas Compressors', 4, 3451),
(3455, 'SIC', 3564, 'Blowers & Fans', 4, 3451),
(3456, 'SIC', 3565, 'Packaging Machinery', 4, 3451),
(3457, 'SIC', 3566, 'Speed Changers, Drives & Gears', 4, 3451),
(3458, 'SIC', 3567, 'Industrial Furnaces & Ovens', 4, 3451),
(3459, 'SIC', 3568, 'Power Transmission Equipment, nec', 4, 3451),
(3460, 'SIC', 3569, 'General Industrial Machinery, nec', 4, 3451),
(3453, 'SIC', 3562, 'Ball & Roller Bearings', 4, 3451),
(2426, 'SEC', 3572, 'Computer Storage Devices', 4, 2424),
(2428, 'SEC', 3577, 'Computer Peripheral Equipment, nec', 4, 2424),
(2429, 'SEC', 3578, 'Calculating & Accounting Equipment', 4, 2424),
(2430, 'SEC', 3579, 'Office Machines, nec', 4, 2424),
(2425, 'SEC', 3571, 'Electronic Computers', 4, 2424),
(2427, 'SEC', 3575, 'Computer Terminals', 4, 2424),
(3462, 'SIC', 3571, 'Electronic Computers', 4, 3461),
(3463, 'SIC', 3572, 'Computer Storage Devices', 4, 3461),
(3464, 'SIC', 3575, 'Computer Terminals', 4, 3461),
(3465, 'SIC', 3577, 'Computer Peripheral Equipment, nec', 4, 3461),
(3466, 'SIC', 3578, 'Calculating & Accounting Equipment', 4, 3461),
(3467, 'SIC', 3579, 'Office Machines, nec', 4, 3461),
(2432, 'SEC', 3585, 'Refrigeration & Heating Equipment', 4, 2431),
(3473, 'SIC', 3589, 'Service Industry Machinery, nec', 4, 3468),
(3472, 'SIC', 3586, 'Measuring & Dispensing Pumps', 4, 3468),
(3469, 'SIC', 3581, 'Automatic Vending Machines', 4, 3468),
(3470, 'SIC', 3582, 'Commercial Laundry Equipment', 4, 3468),
(3471, 'SIC', 3585, 'Refrigeration & Heating Equipment', 4, 3468),
(3475, 'SIC', 3592, 'Carburetors, Piston Rings & Valves', 4, 3474),
(3479, 'SIC', 3599, 'Industrial Machinery, nec', 4, 3474),
(3476, 'SIC', 3593, 'Fluid Power Cylinders & Actuators', 4, 3474),
(3477, 'SIC', 3594, 'Fluid Power Pumps & Motors', 4, 3474),
(3478, 'SIC', 3596, 'Scales & Balances, Except Laboratory', 4, 3474),
(2437, 'SEC', 3613, 'Switchgear & Switchboard Apparatus', 4, 2435),
(2436, 'SEC', 3612, 'Transformers, Except Electronic', 4, 2435),
(3503, 'SIC', 3648, 'Lighting Equipment, nec', 4, 3496),
(3501, 'SIC', 3646, 'Commercial Lighting Fixtures', 4, 3496),
(3500, 'SIC', 3645, 'Residential Lighting Fixtures', 4, 3496),
(3499, 'SIC', 3644, 'Noncurrent-Carrying Wiring Devices', 4, 3496),
(3498, 'SIC', 3643, 'Current-Carrying Wiring Devices', 4, 3496),
(3497, 'SIC', 3641, 'Electric Lamps', 4, 3496),
(2444, 'SEC', 3651, 'Household Audio & Video Equipment', 4, 2443),
(2445, 'SEC', 3652, 'Prerecorded Records & Tapes', 4, 2443),
(3506, 'SIC', 3652, 'Prerecorded Records & Tapes', 4, 3504),
(3505, 'SIC', 3651, 'Household Audio & Video Equipment', 4, 3504),
(2449, 'SEC', 3669, 'Communications Equipment, nec', 4, 2446),
(2447, 'SEC', 3661, 'Telephone & Telegraph Apparatus', 4, 2446),
(2448, 'SEC', 3663, 'Radio & TV Communications Equipment', 4, 2446),
(3508, 'SIC', 3661, 'Telephone & Telegraph Apparatus', 4, 3507),
(3509, 'SIC', 3663, 'Radio & TV Communications Equipment', 4, 3507),
(3510, 'SIC', 3669, 'Communications Equipment, nec', 4, 3507),
(2451, 'SEC', 3672, 'Printed Circuit Boards', 4, 2450),
(2453, 'SEC', 3677, 'Electronic Coils & Transformers', 4, 2450),
(2452, 'SEC', 3674, 'Semiconductors & Related Devices', 4, 2450),
(2454, 'SEC', 3678, 'Electronic Connectors', 4, 2450),
(2455, 'SEC', 3679, 'Electronic Components, nec', 4, 2450),
(3516, 'SIC', 3676, 'Electronic Resistors', 4, 3511),
(3519, 'SIC', 3679, 'Electronic Components, nec', 4, 3511),
(3518, 'SIC', 3678, 'Electronic Connectors', 4, 3511),
(3517, 'SIC', 3677, 'Electronic Coils & Transformers', 4, 3511),
(3515, 'SIC', 3675, 'Electronic Capacitors', 4, 3511),
(3514, 'SIC', 3674, 'Semiconductors & Related Devices', 4, 3511),
(3513, 'SIC', 3672, 'Printed Circuit Boards', 4, 3511),
(3512, 'SIC', 3671, 'Electron Tubes', 4, 3511),
(2457, 'SEC', 3695, 'Magnetic & Optical Recording Media', 4, 2456),
(3521, 'SIC', 3691, 'Storage Batteries', 4, 3520),
(3522, 'SIC', 3692, 'Primary Batteries, Dry & Wet', 4, 3520),
(3523, 'SIC', 3694, 'Engine Electrical Equipment', 4, 3520),
(3524, 'SIC', 3695, 'Magnetic & Optical Recording Media', 4, 3520),
(3525, 'SIC', 3699, 'Electrical Equipment & Supplies, nec', 4, 3520),
(2460, 'SEC', 3711, 'Motor Vehicles & Car Bodies', 4, 2459),
(2464, 'SEC', 3716, 'Motor Homes', 4, 2459),
(2463, 'SEC', 3715, 'Truck Trailers', 4, 2459),
(2462, 'SEC', 3714, 'Motor Vehicle Parts & Accessories', 4, 2459),
(2461, 'SEC', 3713, 'Truck & Bus Bodies', 4, 2459),
(3532, 'SIC', 3716, 'Motor Homes', 4, 3527),
(3528, 'SIC', 3711, 'Motor Vehicles & Car Bodies', 4, 3527),
(3530, 'SIC', 3714, 'Motor Vehicle Parts & Accessories', 4, 3527),
(3531, 'SIC', 3715, 'Truck Trailers', 4, 3527),
(3529, 'SIC', 3713, 'Truck & Bus Bodies', 4, 3527),
(2467, 'SEC', 3724, 'Aircraft Engines & Engine Parts', 4, 2465),
(2468, 'SEC', 3728, 'Aircraft Parts & Equipment, nec', 4, 2465),
(2466, 'SEC', 3721, 'Aircraft', 4, 2465),
(3534, 'SIC', 3721, 'Aircraft', 4, 3533),
(3559, 'SIC', 3824, 'Fluid Meters & Counting Devices', 4, 3555),
(3560, 'SIC', 3825, 'Instruments to Measure Electricity', 4, 3555),
(3561, 'SIC', 3826, 'Analytical Instruments', 4, 3555),
(3563, 'SIC', 3829, 'Measuring & Controlling Devices, nec', 4, 3555),
(3562, 'SIC', 3827, 'Optical Instruments & Lenses', 4, 3555),
(3556, 'SIC', 3821, 'Laboratory Apparatus & Furniture', 4, 3555),
(3557, 'SIC', 3822, 'Environmental Controls', 4, 3555),
(3558, 'SIC', 3823, 'Process Control Instruments', 4, 3555),
(2490, 'SEC', 3842, 'Surgical Appliances & Supplies', 4, 2488),
(2491, 'SEC', 3843, 'Dental Equipment & Supplies', 4, 2488),
(2492, 'SEC', 3844, 'X-Ray Apparatus & Tubes', 4, 2488),
(2493, 'SEC', 3845, 'Electromedical Equipment', 4, 2488),
(2489, 'SEC', 3841, 'Surgical & Medical Instruments', 4, 2488),
(3565, 'SIC', 3841, 'Surgical & Medical Instruments', 4, 3564),
(3566, 'SIC', 3842, 'Surgical Appliances & Supplies', 4, 3564),
(3567, 'SIC', 3843, 'Dental Equipment & Supplies', 4, 3564),
(3568, 'SIC', 3844, 'X-Ray Apparatus & Tubes', 4, 3564),
(3569, 'SIC', 3845, 'Electromedical Equipment', 4, 3564),
(2495, 'SEC', 3851, 'Ophthalmic Goods', 4, 2494),
(3571, 'SIC', 3851, 'Ophthalmic Goods', 4, 3570),
(2497, 'SEC', 3861, 'Photographic Equipment & Supplies', 4, 2496),
(3573, 'SIC', 3861, 'Photographic Equipment & Supplies', 4, 3572),
(2499, 'SEC', 3873, 'Watches, Clocks, Watchcases & Parts', 4, 2498),
(3575, 'SIC', 3873, 'Watches, Clocks, Watchcases & Parts', 4, 3574),
(2502, 'SEC', 3911, 'Jewelry, Precious Metal', 4, 2501),
(3580, 'SIC', 3915, 'Jewelers'' Materials & Lapidary Work', 4, 3577),
(3579, 'SIC', 3914, 'Silverware & Plated Ware', 4, 3577),
(3578, 'SIC', 3911, 'Jewelry, Precious Metal', 4, 3577),
(2504, 'SEC', 3931, 'Musical Instruments', 4, 2503),
(3582, 'SIC', 3931, 'Musical Instruments', 4, 3581),
(3632, 'SIC', 4231, 'Trucking Terminal Facilities', 4, 3631),
(3635, 'SIC', 4311, 'US Postal Service', 4, 3634),
(2541, 'SEC', 4812, 'Radiotelephone Communications', 4, 2540),
(2542, 'SEC', 4813, 'Telephone Communications, Except Radio', 4, 2540),
(3682, 'SIC', 4812, 'Radiotelephone Communications', 4, 3681),
(3683, 'SIC', 4813, 'Telephone Communications, Except Radio', 4, 3681),
(2544, 'SEC', 4822, 'Telegraph & Other Communications', 4, 2543),
(3685, 'SIC', 4822, 'Telegraph & Other Communications', 4, 3684),
(2546, 'SEC', 4832, 'Radio Broadcasting Stations', 4, 2545),
(2547, 'SEC', 4833, 'Television Broadcasting Stations', 4, 2545),
(3688, 'SIC', 4833, 'Television Broadcasting Stations', 4, 3686),
(3687, 'SIC', 4832, 'Radio Broadcasting Stations', 4, 3686),
(2549, 'SEC', 4841, 'Cable & Other Pay TV Services', 4, 2548),
(3690, 'SIC', 4841, 'Cable & Other Pay TV Services', 4, 3689),
(2551, 'SEC', 4899, 'Communications Services, nec', 4, 2550),
(3692, 'SIC', 4899, 'Communications Services, nec', 4, 3691),
(3725, 'SIC', 5031, 'Lumber, Plywood & Millwork', 4, 3724),
(3727, 'SIC', 5033, 'Roofing, Siding & Insulation', 4, 3724),
(2576, 'SEC', 5047, 'Medical & Hospital Equipment', 4, 2574),
(2575, 'SEC', 5045, 'Computers, Peripherals & Software', 4, 2574),
(3732, 'SIC', 5045, 'Computers, Peripherals & Software', 4, 3729),
(3736, 'SIC', 5049, 'Professional Equipment, nec', 4, 3729),
(3735, 'SIC', 5048, 'Ophthalmic Goods', 4, 3729),
(3734, 'SIC', 5047, 'Medical & Hospital Equipment', 4, 3729),
(3733, 'SIC', 5046, 'Commercial Equipment, nec', 4, 3729),
(3731, 'SIC', 5044, 'Office Equipment', 4, 3729),
(3730, 'SIC', 5043, 'Photographic Equipment & Supplies', 4, 3729),
(2578, 'SEC', 5051, 'Metals Service Centers & Offices', 4, 2577),
(3738, 'SIC', 5051, 'Metals Service Centers & Offices', 4, 3737),
(3739, 'SIC', 5052, 'Coal & Other Minerals & Ores', 4, 3737),
(2580, 'SEC', 5063, 'Electrical Apparatus & Equipment', 4, 2579),
(2581, 'SEC', 5064, 'Electrical Appliances, TV & Radios', 4, 2579),
(3758, 'SIC', 5092, 'Toys & Hobby Goods & Supplies', 4, 3756),
(3759, 'SIC', 5093, 'Scrap & Waste Materials', 4, 3756),
(3760, 'SIC', 5094, 'Jewelry & Precious Stones', 4, 3756),
(3757, 'SIC', 5091, 'Sporting & Recreational Goods', 4, 3756),
(3766, 'SIC', 5113, 'Industrial & Personal Service Paper', 4, 3763),
(3764, 'SIC', 5111, 'Printing & Writing Paper', 4, 3763),
(3765, 'SIC', 5112, 'Stationery & Office Supplies', 4, 3763),
(2594, 'SEC', 5122, 'Drugs, Proprietaries & Sundries', 4, 2593),
(3768, 'SIC', 5122, 'Drugs, Proprietaries & Sundries', 4, 3767),
(3770, 'SIC', 5131, 'Piece Goods & Notations', 4, 3769),
(3773, 'SIC', 5139, 'Footwear', 4, 3769),
(3772, 'SIC', 5137, 'Women''s & Children''s Clothing', 4, 3769),
(3771, 'SIC', 5136, 'Men''s & Boys'' Clothing', 4, 3769),
(2597, 'SEC', 5141, 'Groceries, General Line', 4, 2596),
(3775, 'SIC', 5141, 'Groceries, General Line', 4, 3774),
(3776, 'SIC', 5142, 'Packaged Frozen Foods', 4, 3774),
(3777, 'SIC', 5143, 'Dairy Products, Except Dried or Canned', 4, 3774),
(3778, 'SIC', 5144, 'Poultry & Poultry Products', 4, 3774),
(3779, 'SIC', 5145, 'Confectionery', 4, 3774),
(3780, 'SIC', 5146, 'Fish & Seafoods', 4, 3774),
(3781, 'SIC', 5147, 'Meat & Meat Products', 4, 3774),
(3783, 'SIC', 5149, 'Groceries & Related Products, nec', 4, 3774),
(3782, 'SIC', 5148, 'Fresh Fruits & Vegetables', 4, 3774),
(3786, 'SIC', 5154, 'Livestock', 4, 3784),
(3785, 'SIC', 5153, 'Grain & Field Beans', 4, 3784),
(3787, 'SIC', 5159, 'Farm-Product Raw Materials, nec', 4, 3784),
(3789, 'SIC', 5162, 'Plastics Materials & Basic Shapes', 4, 3788),
(3790, 'SIC', 5169, 'Chemicals & Allied Products, nec', 4, 3788),
(2601, 'SEC', 5171, 'Petroleum Bulk Stations &Terminals', 4, 2600),
(2602, 'SEC', 5172, 'Petroleum Products, nec', 4, 2600),
(3793, 'SIC', 5172, 'Petroleum Products, nec', 4, 3791),
(3792, 'SIC', 5171, 'Petroleum Bulk Stations &Terminals', 4, 3791),
(3796, 'SIC', 5182, 'Wines & Distilled Beverages', 4, 3794),
(3795, 'SIC', 5181, 'Beer & Ale', 4, 3794),
(3800, 'SIC', 5193, 'Flowers & Florists'' Supplies', 4, 3797),
(3798, 'SIC', 5191, 'Farm Supplies', 4, 3797),
(3799, 'SIC', 5192, 'Books, Periodicals & Newspapers', 4, 3797),
(3803, 'SIC', 5199, 'Nondurable Goods, nec', 4, 3797),
(3802, 'SIC', 5198, 'Paints, Varnishes & Supplies', 4, 3797),
(3801, 'SIC', 5194, 'Tobacco & Tobacco Products', 4, 3797),
(3890, 'SIC', 5921, 'Liquor Stores', 4, 3889),
(3892, 'SIC', 5932, 'Used Merchandise Stores', 4, 3891),
(2644, 'SEC', 5944, 'Jewelers Stores', 4, 2643),
(2645, 'SEC', 5945, 'Hobby, Toy & Game Shops', 4, 2643),
(3896, 'SIC', 5943, 'Stationary Stores', 4, 3893),
(3895, 'SIC', 5942, 'Book Stores', 4, 3893),
(3894, 'SIC', 5941, 'Sporting Goods & Bicycle Shops', 4, 3893),
(3897, 'SIC', 5944, 'Jewelers Stores', 4, 3893),
(3902, 'SIC', 5949, 'Sewing, Needlework & Piece Goods', 4, 3893),
(3901, 'SIC', 5948, 'Luggage & Leather Goods Stores', 4, 3893),
(3900, 'SIC', 5947, 'Gift, Novelty & Souvenir Shops', 4, 3893),
(3899, 'SIC', 5946, 'Camera & Photographic Supply Stores', 4, 3893),
(3898, 'SIC', 5945, 'Hobby, Toy & Game Shops', 4, 3893),
(2647, 'SEC', 5961, 'Catalog & Mail Order Houses', 4, 2646),
(3906, 'SIC', 5963, 'Direct Selling Establishments', 4, 3903),
(3905, 'SIC', 5962, 'Merchandising Machine Operators', 4, 3903),
(3904, 'SIC', 5961, 'Catalog & Mail Order Houses', 4, 3903),
(3910, 'SIC', 5989, 'Fuel Dealers, nec', 4, 3907),
(3909, 'SIC', 5984, 'Liquefied Petroleum Gas Dealers', 4, 3907),
(3908, 'SIC', 5983, 'Fuel Oil Dealers', 4, 3907),
(3915, 'SIC', 5995, 'Optical Goods Stores', 4, 3911),
(3912, 'SIC', 5992, 'Florists', 4, 3911),
(3913, 'SIC', 5993, 'Tobacco Stores & Stands', 4, 3911),
(3914, 'SIC', 5994, 'News Dealers & News Stands', 4, 3911),
(3916, 'SIC', 5999, 'Miscellaneous Retail Stores, nec', 4, 3911),
(3998, 'SIC', 6726, 'Investment Offices, nec', 4, 3996),
(3997, 'SIC', 6722, 'Management Investment Open-End', 4, 3996),
(4000, 'SIC', 6732, 'Education, Religious, Etc. Trusts', 4, 3999),
(4001, 'SIC', 6733, 'Trusts, nec', 4, 3999),
(2706, 'SEC', 6794, 'Patent Owners & Lessors', 4, 2704),
(2705, 'SEC', 6792, 'Oil Royalty Traders', 4, 2704),
(2707, 'SEC', 6798, 'Real Estate Investment Trusts', 4, 2704),
(2708, 'SEC', 6799, 'Investors, nec', 4, 2704),
(4004, 'SIC', 6794, 'Patent Owners & Lessors', 4, 4002),
(4003, 'SIC', 6792, 'Oil Royalty Traders', 4, 4002),
(4005, 'SIC', 6798, 'Real Estate Investment Trusts', 4, 4002),
(4006, 'SIC', 6799, 'Investors, nec', 4, 4002),
(4067, 'SIC', 7372, 'Prepackaged Software', 4, 4065),
(4074, 'SIC', 7379, 'Computer Related Services, nec', 4, 4065),
(4066, 'SIC', 7371, 'Computer Programming Services', 4, 4065),
(4073, 'SIC', 7378, 'Computer Maintenance & Repair', 4, 4065),
(4072, 'SIC', 7377, 'Computer Rental & Leasing', 4, 4065),
(4070, 'SIC', 7375, 'Information Retrieval Services', 4, 4065),
(2732, 'SEC', 7381, 'Detective & Armored Car Services', 4, 2731),
(2733, 'SEC', 7384, 'Photo Finishing Laboratories', 4, 2731),
(2734, 'SEC', 7389, 'Trade Shows & Fairs', 4, 2731),
(4077, 'SIC', 7382, 'Security Systems Services', 4, 4075),
(4080, 'SIC', 7389, 'Trade Shows & Fairs', 4, 4075),
(4078, 'SIC', 7383, 'News Syndicates', 4, 4075),
(4076, 'SIC', 7381, 'Detective & Armored Car Services', 4, 4075),
(4079, 'SIC', 7384, 'Photo Finishing Laboratories', 4, 4075),
(4083, 'SIC', 7513, 'Truck Rental & Leasing, No Drivers', 4, 4082),
(4086, 'SIC', 7519, 'Utility Trailer Rental', 4, 4082),
(4085, 'SIC', 7515, 'Passenger Car Leasing', 4, 4082),
(4084, 'SIC', 7514, 'Passenger Car Rental', 4, 4082),
(4088, 'SIC', 7521, 'Automobile Parking', 4, 4087),
(4091, 'SIC', 7533, 'Auto Exhaust System Repair Shops', 4, 4089),
(4093, 'SIC', 7536, 'Automotive Glass Replacement Shops', 4, 4089),
(4092, 'SIC', 7534, 'Tire Retreading & Repair Shops', 4, 4089),
(4096, 'SIC', 7539, 'Automotive Repair Shops, nec', 4, 4089),
(4095, 'SIC', 7538, 'General Automotive Repair Shops', 4, 4089),
(4094, 'SIC', 7537, 'Automotive Transmission Repair Shops', 4, 4089),
(4090, 'SIC', 7532, 'Top & Body Repair & Paint Shops', 4, 4089),
(4099, 'SIC', 7549, 'Automotive Services, nec', 4, 4097),
(4098, 'SIC', 7542, 'Carwashes', 4, 4097),
(4102, 'SIC', 7622, 'Radio & Television Repair', 4, 4101),
(4103, 'SIC', 7623, 'Refrigeration Service & Repair', 4, 4101),
(4104, 'SIC', 7629, 'Electrical Repair Shops, nec', 4, 4101),
(4106, 'SIC', 7631, 'Watch, Clock & Jewelry Repair', 4, 4105),
(4108, 'SIC', 7641, 'Reupholstery & Furniture Repair', 4, 4107),
(4112, 'SIC', 7699, 'Repair Services, nec', 4, 4109),
(4111, 'SIC', 7694, 'Armatures Rewinding Shops', 4, 4109),
(4110, 'SIC', 7692, 'Welding Repair', 4, 4109),
(2740, 'SEC', 7812, 'Motion Picture & Video Production', 4, 2739),
(2741, 'SEC', 7819, 'Services Allied to Motion Pictures', 4, 2739),
(4115, 'SIC', 7812, 'Motion Picture & Video Production', 4, 4114),
(4116, 'SIC', 7819, 'Services Allied to Motion Pictures', 4, 4114),
(2743, 'SEC', 7822, 'Motion Picture & Tape Distribution', 4, 2742),
(2744, 'SEC', 7829, 'Motion Picture Distribution Services', 4, 2742),
(4155, 'SIC', 8042, 'Offices & Clinics of Optometrists', 4, 4153),
(4154, 'SIC', 8041, 'Offices & Clinics of Chiropractors', 4, 4153),
(2757, 'SEC', 8051, 'Skilled Nursing Care Facilities', 4, 2756),
(4159, 'SIC', 8051, 'Skilled Nursing Care Facilities', 4, 4158),
(4161, 'SIC', 8059, 'Nursing & Personal Care, nec', 4, 4158),
(4160, 'SIC', 8052, 'Intermediate Care Facilities', 4, 4158),
(2759, 'SEC', 8062, 'General Medical & Surgical Hospitals', 4, 2758),
(4163, 'SIC', 8062, 'General Medical & Surgical Hospitals', 4, 4162),
(4164, 'SIC', 8063, 'Psychiatric Hospitals', 4, 4162),
(4165, 'SIC', 8069, 'Specialty Hospitals, Except Psychiatric', 4, 4162),
(2761, 'SEC', 8071, 'Medical Laboratories', 4, 2760),
(4168, 'SIC', 8072, 'Dental Laboratories', 4, 4166),
(4167, 'SIC', 8071, 'Medical Laboratories', 4, 4166),
(2763, 'SEC', 8082, 'Home Health Care Services', 4, 2762),
(4170, 'SIC', 8082, 'Home Health Care Services', 4, 4169),
(2765, 'SEC', 8093, 'Specialty Outpatient Clinics, nec', 4, 2764),
(4173, 'SIC', 8093, 'Specialty Outpatient Clinics, nec', 4, 4171),
(4172, 'SIC', 8092, 'Kidney Dialysis Centers', 4, 4171),
(4174, 'SIC', 8099, 'Health & Allied Services, nec', 4, 4171),
(2768, 'SEC', 8111, 'Legal Services', 4, 2767),
(4177, 'SIC', 8111, 'Legal Services', 4, 4176),
(4238, 'SIC', 8743, 'Public Relations Services', 4, 4235),
(4236, 'SIC', 8741, 'Management Services', 4, 4235),
(4237, 'SIC', 8742, 'Management Consulting Services', 4, 4235),
(4239, 'SIC', 8744, 'Facilities Support Services', 4, 4235),
(4240, 'SIC', 8748, 'Business Consulting, nec', 4, 4235),
(4243, 'SIC', 8811, 'Private Households', 4, 4242),
(4246, 'SIC', 8999, 'Services, nec', 4, 4245),
(4292, 'SIC', 9641, 'Regulation of Agricultural Marketing', 4, 4291),
(4294, 'SIC', 9651, 'Regulation Misc. Commercial Sectors', 4, 4293),
(4296, 'SIC', 9661, 'Space Research & Technology', 4, 4295),
(4299, 'SIC', 9711, 'National Security', 4, 4298),
(2787, 'SEC', 9721, 'International Affairs', 4, 2786),
(4301, 'SIC', 9721, 'International Affairs', 4, 4300),
(4304, 'SIC', 9999, 'Nonclassifiable Establishments', 4, 4303),
(56, 'NAICS', 112, 'Animal Production and Aquaculture', 2, 1),
(108, 'NAICS', 114, 'Fishing, Hunting and Trapping', 2, 1),
(2, 'NAICS', 111, 'Crop Production', 2, 1),
(117, 'NAICS', 115, 'Support Activities for Agriculture and Forestry', 2, 1),
(3, 'NAICS', 1111, 'Oilseed and Grain Farming', 3, 2),
(23, 'NAICS', 1113, 'Fruit and Tree Nut Farming', 3, 2),
(43, 'NAICS', 1119, 'Other Crop Farming', 3, 2),
(19, 'NAICS', 1112, 'Vegetable and Melon Farming', 3, 2),
(36, 'NAICS', 1114, 'Greenhouse, Nursery, and Floriculture Production', 3, 2),
(11, 'NAICS', 11114, 'Wheat Farming', 4, 3),
(5, 'NAICS', 11111, 'Soybean Farming', 4, 3),
(13, 'NAICS', 11115, 'Corn Farming', 4, 3),
(15, 'NAICS', 11116, 'Rice Farming', 4, 3),
(16, 'NAICS', 11119, 'Other Grain Farming', 4, 3),
(7, 'NAICS', 11112, 'Oilseed (except Soybean) Farming', 4, 3),
(9, 'NAICS', 11113, 'Dry Pea and Bean Farming', 4, 3),
(4, 'NAICS', 111110, 'Soybean Farming', 5, 5),
(6, 'NAICS', 111120, 'Oilseed (except Soybean) Farming', 5, 7),
(8, 'NAICS', 111130, 'Dry Pea and Bean Farming', 5, 9),
(10, 'NAICS', 111140, 'Wheat Farming', 5, 11),
(14, 'NAICS', 111160, 'Rice Farming', 5, 15),
(17, 'NAICS', 111191, 'Oilseed and Grain Combination Farming', 5, 16),
(18, 'NAICS', 111199, 'All Other Grain Farming', 5, 16),
(20, 'NAICS', 11121, 'Vegetable and Melon Farming', 4, 19),
(21, 'NAICS', 111211, 'Potato Farming', 5, 20),
(4257, 'SIC', 9210, 'Courts', 3, 4256),
(22, 'NAICS', 111219, 'Other Vegetable (except Potato) and Melon Farming', 5, 20),
(28, 'NAICS', 11133, 'Noncitrus Fruit and Tree Nut Farming', 4, 23),
(27, 'NAICS', 11132, 'Citrus (except Orange) Groves', 4, 23),
(25, 'NAICS', 11131, 'Orange Groves', 4, 23),
(24, 'NAICS', 111310, 'Orange Groves', 5, 25),
(26, 'NAICS', 111320, 'Citrus (except Orange) Groves', 5, 27),
(32, 'NAICS', 111334, 'Berry (except Strawberry) Farming', 5, 28),
(33, 'NAICS', 111335, 'Tree Nut Farming', 5, 28),
(34, 'NAICS', 111336, 'Fruit and Tree Nut Combination Farming', 5, 28),
(30, 'NAICS', 111332, 'Grape Vineyards', 5, 28),
(29, 'NAICS', 111331, 'Apple Orchards', 5, 28),
(35, 'NAICS', 111339, 'Other Noncitrus Fruit Farming', 5, 28),
(31, 'NAICS', 111333, 'Strawberry Farming', 5, 28),
(37, 'NAICS', 11141, 'Food Crops Grown Under Cover', 4, 36),
(40, 'NAICS', 11142, 'Nursery and Floriculture Production', 4, 36),
(39, 'NAICS', 111419, 'Other Food Crops Grown Under Cover', 5, 37),
(38, 'NAICS', 111411, 'Mushroom Production', 5, 37),
(42, 'NAICS', 111422, 'Floriculture Production', 5, 40),
(41, 'NAICS', 111421, 'Nursery and Tree Production', 5, 40),
(51, 'NAICS', 11194, 'Hay Farming', 4, 43),
(45, 'NAICS', 11191, 'Tobacco Farming', 4, 43),
(47, 'NAICS', 11192, 'Cotton Farming', 4, 43),
(49, 'NAICS', 11193, 'Sugarcane Farming', 4, 43),
(52, 'NAICS', 11199, 'All Other Crop Farming', 4, 43),
(44, 'NAICS', 111910, 'Tobacco Farming', 5, 45),
(46, 'NAICS', 111920, 'Cotton Farming', 5, 47),
(48, 'NAICS', 111930, 'Sugarcane Farming', 5, 49),
(50, 'NAICS', 111940, 'Hay Farming', 5, 51),
(53, 'NAICS', 111991, 'Sugar Beet Farming', 5, 52),
(55, 'NAICS', 111998, 'All Other Miscellaneous Crop Farming', 5, 52),
(54, 'NAICS', 111992, 'Peanut Farming', 5, 52),
(68, 'NAICS', 1123, 'Poultry and Egg Production', 3, 56),
(65, 'NAICS', 1122, 'Hog and Pig Farming', 3, 56),
(89, 'NAICS', 1129, 'Other Animal Production', 3, 56),
(84, 'NAICS', 1125, 'Aquaculture', 3, 56),
(79, 'NAICS', 1124, 'Sheep and Goat Farming', 3, 56),
(57, 'NAICS', 1121, 'Cattle Ranching and Farming', 3, 56),
(62, 'NAICS', 11212, 'Dairy Cattle and Milk Production', 4, 57),
(64, 'NAICS', 11213, 'Dual-Purpose Cattle Ranching and Farming', 4, 57),
(58, 'NAICS', 11211, 'Beef Cattle Ranching and Farming, including Feedlots', 4, 57),
(59, 'NAICS', 112111, 'Beef Cattle Ranching and Farming', 5, 58),
(60, 'NAICS', 112112, 'Cattle Feedlots', 5, 58),
(61, 'NAICS', 112120, 'Dairy Cattle and Milk Production', 5, 62),
(63, 'NAICS', 112130, 'Dual-Purpose Cattle Ranching and Farming', 5, 64),
(67, 'NAICS', 11221, 'Hog and Pig Farming', 4, 65),
(66, 'NAICS', 112210, 'Hog and Pig Farming', 5, 67),
(70, 'NAICS', 11231, 'Chicken Egg Production', 4, 68),
(72, 'NAICS', 11232, 'Broilers and Other Meat Type Chicken Production', 4, 68),
(76, 'NAICS', 11234, 'Poultry Hatcheries', 4, 68),
(78, 'NAICS', 11239, 'Other Poultry Production', 4, 68),
(74, 'NAICS', 11233, 'Turkey Production', 4, 68),
(69, 'NAICS', 112310, 'Chicken Egg Production', 5, 70),
(71, 'NAICS', 112320, 'Broilers and Other Meat Type Chicken Production', 5, 72),
(73, 'NAICS', 112330, 'Turkey Production', 5, 74),
(75, 'NAICS', 112340, 'Poultry Hatcheries', 5, 76),
(77, 'NAICS', 112390, 'Other Poultry Production', 5, 78),
(81, 'NAICS', 11241, 'Sheep Farming', 4, 79),
(83, 'NAICS', 11242, 'Goat Farming', 4, 79),
(80, 'NAICS', 112410, 'Sheep Farming', 5, 81),
(82, 'NAICS', 112420, 'Goat Farming', 5, 83),
(85, 'NAICS', 11251, 'Aquaculture', 4, 84),
(88, 'NAICS', 112519, 'Other Aquaculture', 5, 85),
(86, 'NAICS', 112511, 'Finfish Farming and Fish Hatcheries', 5, 85),
(87, 'NAICS', 112512, 'Shellfish Farming', 5, 85),
(95, 'NAICS', 11293, 'Fur-Bearing Animal and Rabbit Production', 4, 89),
(97, 'NAICS', 11299, 'All Other Animal Production', 4, 89),
(93, 'NAICS', 11292, 'Horses and Other Equine Production', 4, 89),
(91, 'NAICS', 11291, 'Apiculture', 4, 89),
(90, 'NAICS', 112910, 'Apiculture', 5, 91),
(92, 'NAICS', 112920, 'Horses and Other Equine Production', 5, 93),
(94, 'NAICS', 112930, 'Fur-Bearing Animal and Rabbit Production', 5, 95),
(96, 'NAICS', 112990, 'All Other Animal Production', 5, 97),
(102, 'NAICS', 1132, 'Forest Nurseries and Gathering of Forest Products', 3, 98),
(99, 'NAICS', 1131, 'Timber Tract Operations', 3, 98),
(101, 'NAICS', 11311, 'Timber Tract Operations', 4, 99),
(100, 'NAICS', 113110, 'Timber Tract Operations', 5, 101),
(104, 'NAICS', 11321, 'Forest Nurseries and Gathering of Forest Products', 4, 102),
(103, 'NAICS', 113210, 'Forest Nurseries and Gathering of Forest Products', 5, 104),
(106, 'NAICS', 113310, 'Logging', 5, 107),
(109, 'NAICS', 1141, 'Fishing', 3, 108),
(114, 'NAICS', 1142, 'Hunting and Trapping', 3, 108),
(110, 'NAICS', 11411, 'Fishing', 4, 109),
(113, 'NAICS', 114119, 'Other Marine Fishing', 5, 110),
(111, 'NAICS', 114111, 'Finfish Fishing', 5, 110),
(112, 'NAICS', 114112, 'Shellfish Fishing', 5, 110),
(116, 'NAICS', 11421, 'Hunting and Trapping', 4, 114),
(115, 'NAICS', 114210, 'Hunting and Trapping', 5, 116),
(129, 'NAICS', 1153, 'Support Activities for Forestry', 3, 117),
(126, 'NAICS', 1152, 'Support Activities for Animal Production', 3, 117),
(118, 'NAICS', 1151, 'Support Activities for Crop Production', 3, 117),
(119, 'NAICS', 11511, 'Support Activities for Crop Production', 4, 118),
(120, 'NAICS', 115111, 'Cotton Ginning', 5, 119),
(125, 'NAICS', 115116, 'Farm Management Services', 5, 119),
(124, 'NAICS', 115115, 'Farm Labor Contractors and Crew Leaders', 5, 119),
(123, 'NAICS', 115114, 'Postharvest Crop Activities (except Cotton Ginning)', 5, 119),
(122, 'NAICS', 115113, 'Crop Harvesting, Primarily by Machine', 5, 119),
(121, 'NAICS', 115112, 'Soil Preparation, Planting, and Cultivating', 5, 119),
(128, 'NAICS', 11521, 'Support Activities for Animal Production', 4, 126),
(127, 'NAICS', 115210, 'Support Activities for Animal Production', 5, 128),
(131, 'NAICS', 11531, 'Support Activities for Forestry', 4, 129),
(130, 'NAICS', 115310, 'Support Activities for Forestry', 5, 131),
(172, 'NAICS', 213, 'Support Activities for Mining', 2, 132),
(133, 'NAICS', 211, 'Oil and Gas Extraction', 2, 132),
(138, 'NAICS', 212, 'Mining (except Oil and Gas)', 2, 132),
(134, 'NAICS', 2111, 'Oil and Gas Extraction', 3, 133),
(135, 'NAICS', 21111, 'Oil and Gas Extraction', 4, 134),
(137, 'NAICS', 211112, 'Natural Gas Liquid Extraction', 5, 135),
(136, 'NAICS', 211111, 'Crude Petroleum and Natural Gas Extraction', 5, 135),
(156, 'NAICS', 2123, 'Nonmetallic Mineral Mining and Quarrying', 3, 138),
(144, 'NAICS', 2122, 'Metal Ore Mining', 3, 138),
(139, 'NAICS', 2121, 'Coal Mining', 3, 138),
(140, 'NAICS', 21211, 'Coal Mining', 4, 139),
(143, 'NAICS', 212113, 'Anthracite Mining', 5, 140),
(142, 'NAICS', 212112, 'Bituminous Coal Underground Mining', 5, 140),
(141, 'NAICS', 212111, 'Bituminous Coal and Lignite Surface Mining', 5, 140),
(153, 'NAICS', 21229, 'Other Metal Ore Mining', 4, 144),
(150, 'NAICS', 21223, 'Copper, Nickel, Lead, and Zinc Mining', 4, 144),
(147, 'NAICS', 21222, 'Gold Ore and Silver Ore Mining', 4, 144),
(146, 'NAICS', 21221, 'Iron Ore Mining', 4, 144),
(145, 'NAICS', 212210, 'Iron Ore Mining', 5, 146),
(148, 'NAICS', 212221, 'Gold Ore Mining', 5, 147),
(149, 'NAICS', 212222, 'Silver Ore Mining', 5, 147),
(151, 'NAICS', 212231, 'Lead Ore and Zinc Ore Mining', 5, 150),
(152, 'NAICS', 212234, 'Copper Ore and Nickel Ore Mining', 5, 150),
(155, 'NAICS', 212299, 'All Other Metal Ore Mining', 5, 153),
(154, 'NAICS', 212291, 'Uranium-Radium-Vanadium Ore Mining', 5, 153),
(162, 'NAICS', 21232, 'Sand, Gravel, Clay, and Ceramic and Refractory Minerals Mining and Quarrying', 4, 156),
(167, 'NAICS', 21239, 'Other Nonmetallic Mineral Mining and Quarrying', 4, 156),
(157, 'NAICS', 21231, 'Stone Mining and Quarrying', 4, 156),
(159, 'NAICS', 212312, 'Crushed and Broken Limestone Mining and Quarrying', 5, 157),
(160, 'NAICS', 212313, 'Crushed and Broken Granite Mining and Quarrying', 5, 157),
(161, 'NAICS', 212319, 'Other Crushed and Broken Stone Mining and Quarrying', 5, 157),
(158, 'NAICS', 212311, 'Dimension Stone Mining and Quarrying', 5, 157),
(163, 'NAICS', 212321, 'Construction Sand and Gravel Mining', 5, 162),
(166, 'NAICS', 212325, 'Clay and Ceramic and Refractory Minerals Mining', 5, 162),
(165, 'NAICS', 212324, 'Kaolin and Ball Clay Mining', 5, 162),
(164, 'NAICS', 212322, 'Industrial Sand Mining', 5, 162),
(170, 'NAICS', 212393, 'Other Chemical and Fertilizer Mineral Mining', 5, 167),
(169, 'NAICS', 212392, 'Phosphate Rock Mining', 5, 167),
(171, 'NAICS', 212399, 'All Other Nonmetallic Mineral Mining', 5, 167),
(168, 'NAICS', 212391, 'Potash, Soda, and Borate Mineral Mining', 5, 167),
(173, 'NAICS', 2131, 'Support Activities for Mining', 3, 172),
(174, 'NAICS', 21311, 'Support Activities for Mining', 4, 173),
(176, 'NAICS', 213112, 'Support Activities for Oil and Gas Operations', 5, 174),
(178, 'NAICS', 213114, 'Support Activities for Metal Mining', 5, 174),
(179, 'NAICS', 213115, 'Support Activities for Nonmetallic Minerals (except Fuels) Mining', 5, 174),
(296, 'NAICS', 31131, 'Sugar Manufacturing', 4, 295),
(177, 'NAICS', 213113, 'Support Activities for Coal Mining', 5, 174),
(175, 'NAICS', 213111, 'Drilling Oil and Gas Wells', 5, 174),
(181, 'NAICS', 221, 'Utilities', 2, 180),
(182, 'NAICS', 2211, 'Electric Power Generation, Transmission and Distribution', 3, 181),
(195, 'NAICS', 2212, 'Natural Gas Distribution', 3, 181),
(198, 'NAICS', 2213, 'Water, Sewage and Other Systems', 3, 181),
(192, 'NAICS', 22112, 'Electric Power Transmission, Control, and Distribution', 4, 182),
(183, 'NAICS', 22111, 'Electric Power Generation', 4, 182),
(190, 'NAICS', 221117, 'Biomass Electric Power Generation', 5, 183),
(184, 'NAICS', 221111, 'Hydroelectric Power Generation', 5, 183),
(185, 'NAICS', 221112, 'Fossil Fuel Electric Power Generation', 5, 183),
(186, 'NAICS', 221113, 'Nuclear Electric Power Generation', 5, 183),
(187, 'NAICS', 221114, 'Solar Electric Power Generation', 5, 183),
(188, 'NAICS', 221115, 'Wind Electric Power Generation', 5, 183),
(189, 'NAICS', 221116, 'Geothermal Electric Power Generation', 5, 183),
(191, 'NAICS', 221118, 'Other Electric Power Generation', 5, 183),
(193, 'NAICS', 221121, 'Electric Bulk Power Transmission and Control', 5, 192),
(194, 'NAICS', 221122, 'Electric Power Distribution', 5, 192),
(197, 'NAICS', 22121, 'Natural Gas Distribution', 4, 195),
(196, 'NAICS', 221210, 'Natural Gas Distribution', 5, 197),
(204, 'NAICS', 22133, 'Steam and Air-Conditioning Supply', 4, 198),
(200, 'NAICS', 22131, 'Water Supply and Irrigation Systems', 4, 198),
(202, 'NAICS', 22132, 'Sewage Treatment Facilities', 4, 198),
(199, 'NAICS', 221310, 'Water Supply and Irrigation Systems', 5, 200),
(201, 'NAICS', 221320, 'Sewage Treatment Facilities', 5, 202),
(203, 'NAICS', 221330, 'Steam and Air-Conditioning Supply', 5, 204),
(206, 'NAICS', 236, 'Construction of Buildings', 2, 205),
(235, 'NAICS', 238, 'Specialty Trade Contractors', 2, 205),
(218, 'NAICS', 237, 'Heavy and Civil Engineering Construction', 2, 205),
(213, 'NAICS', 2362, 'Nonresidential Building Construction', 3, 206),
(207, 'NAICS', 2361, 'Residential Building Construction', 3, 206),
(208, 'NAICS', 23611, 'Residential Building Construction', 4, 207),
(209, 'NAICS', 236115, 'New Single-Family Housing Construction (except For-Sale Builders)', 5, 208),
(210, 'NAICS', 236116, 'New Multifamily Housing Construction (except For-Sale Builders)', 5, 208),
(211, 'NAICS', 236117, 'New Housing For-Sale Builders', 5, 208),
(212, 'NAICS', 236118, 'Residential Remodelers', 5, 208),
(217, 'NAICS', 23622, 'Commercial and Institutional Building Construction', 4, 213),
(215, 'NAICS', 23621, 'Industrial Building Construction', 4, 213),
(214, 'NAICS', 236210, 'Industrial Building Construction', 5, 215),
(216, 'NAICS', 236220, 'Commercial and Institutional Building Construction', 5, 217),
(229, 'NAICS', 2373, 'Highway, Street, and Bridge Construction', 3, 218),
(232, 'NAICS', 2379, 'Other Heavy and Civil Engineering Construction', 3, 218),
(219, 'NAICS', 2371, 'Utility System Construction', 3, 218),
(226, 'NAICS', 2372, 'Land Subdivision', 3, 218),
(225, 'NAICS', 23713, 'Power and Communication Line and Related Structures Construction', 4, 219),
(221, 'NAICS', 23711, 'Water and Sewer Line and Related Structures Construction', 4, 219),
(223, 'NAICS', 23712, 'Oil and Gas Pipeline and Related Structures Construction', 4, 219),
(220, 'NAICS', 237110, 'Water and Sewer Line and Related Structures Construction', 5, 221),
(222, 'NAICS', 237120, 'Oil and Gas Pipeline and Related Structures Construction', 5, 223),
(224, 'NAICS', 237130, 'Power and Communication Line and Related Structures Construction', 5, 225),
(228, 'NAICS', 23721, 'Land Subdivision', 4, 226),
(227, 'NAICS', 237210, 'Land Subdivision', 5, 228),
(231, 'NAICS', 23731, 'Highway, Street, and Bridge Construction', 4, 229),
(230, 'NAICS', 237310, 'Highway, Street, and Bridge Construction', 5, 231),
(234, 'NAICS', 23799, 'Other Heavy and Civil Engineering Construction', 4, 232),
(233, 'NAICS', 237990, 'Other Heavy and Civil Engineering Construction', 5, 234),
(253, 'NAICS', 2382, 'Building Equipment Contractors', 3, 235),
(273, 'NAICS', 2389, 'Other Specialty Trade Contractors', 3, 235),
(260, 'NAICS', 2383, 'Building Finishing Contractors', 3, 235),
(236, 'NAICS', 2381, 'Foundation, Structure, and Building Exterior Contractors', 3, 235),
(246, 'NAICS', 23815, 'Glass and Glazing Contractors', 4, 236),
(252, 'NAICS', 23819, 'Other Foundation, Structure, and Building Exterior Contractors', 4, 236),
(238, 'NAICS', 23811, 'Poured Concrete Foundation and Structure Contractors', 4, 236),
(250, 'NAICS', 23817, 'Siding Contractors', 4, 236),
(240, 'NAICS', 23812, 'Structural Steel and Precast Concrete Contractors', 4, 236),
(248, 'NAICS', 23816, 'Roofing Contractors', 4, 236),
(242, 'NAICS', 23813, 'Framing Contractors', 4, 236),
(244, 'NAICS', 23814, 'Masonry Contractors', 4, 236),
(237, 'NAICS', 238110, 'Poured Concrete Foundation and Structure Contractors', 5, 238),
(239, 'NAICS', 238120, 'Structural Steel and Precast Concrete Contractors', 5, 240),
(241, 'NAICS', 238130, 'Framing Contractors', 5, 242),
(243, 'NAICS', 238140, 'Masonry Contractors', 5, 244),
(245, 'NAICS', 238150, 'Glass and Glazing Contractors', 5, 246),
(247, 'NAICS', 238160, 'Roofing Contractors', 5, 248),
(249, 'NAICS', 238170, 'Siding Contractors', 5, 250),
(251, 'NAICS', 238190, 'Other Foundation, Structure, and Building Exterior Contractors', 5, 252),
(259, 'NAICS', 23829, 'Other Building Equipment Contractors', 4, 253),
(255, 'NAICS', 23821, 'Electrical Contractors and Other Wiring Installation Contractors', 4, 253),
(257, 'NAICS', 23822, 'Plumbing, Heating, and Air-Conditioning Contractors', 4, 253),
(254, 'NAICS', 238210, 'Electrical Contractors and Other Wiring Installation Contractors', 5, 255),
(256, 'NAICS', 238220, 'Plumbing, Heating, and Air-Conditioning Contractors', 5, 257),
(258, 'NAICS', 238290, 'Other Building Equipment Contractors', 5, 259),
(268, 'NAICS', 23834, 'Tile and Terrazzo Contractors', 4, 260),
(266, 'NAICS', 23833, 'Flooring Contractors', 4, 260),
(272, 'NAICS', 23839, 'Other Building Finishing Contractors', 4, 260),
(270, 'NAICS', 23835, 'Finish Carpentry Contractors', 4, 260),
(264, 'NAICS', 23832, 'Painting and Wall Covering Contractors', 4, 260),
(262, 'NAICS', 23831, 'Drywall and Insulation Contractors', 4, 260),
(261, 'NAICS', 238310, 'Drywall and Insulation Contractors', 5, 262),
(263, 'NAICS', 238320, 'Painting and Wall Covering Contractors', 5, 264),
(265, 'NAICS', 238330, 'Flooring Contractors', 5, 266),
(267, 'NAICS', 238340, 'Tile and Terrazzo Contractors', 5, 268),
(269, 'NAICS', 238350, 'Finish Carpentry Contractors', 5, 270),
(271, 'NAICS', 238390, 'Other Building Finishing Contractors', 5, 272),
(275, 'NAICS', 23891, 'Site Preparation Contractors', 4, 273),
(277, 'NAICS', 23899, 'All Other Specialty Trade Contractors', 4, 273),
(274, 'NAICS', 238910, 'Site Preparation Contractors', 5, 275),
(276, 'NAICS', 238990, 'All Other Specialty Trade Contractors', 5, 277),
(353, 'NAICS', 312, 'Beverage and Tobacco Product Manufacturing', 2, 278),
(904, 'NAICS', 339, 'Miscellaneous Manufacturing', 2, 278),
(883, 'NAICS', 337, 'Furniture and Related Product Manufacturing', 2, 278),
(833, 'NAICS', 336, 'Transportation Equipment Manufacturing', 2, 278),
(798, 'NAICS', 335, 'Electrical Equipment, Appliance, and Component Manufacturing', 2, 278),
(279, 'NAICS', 311, 'Food Manufacturing', 2, 278),
(759, 'NAICS', 334, 'Computer and Electronic Product Manufacturing', 2, 278),
(386, 'NAICS', 314, 'Textile Product Mills', 2, 278),
(398, 'NAICS', 315, 'Apparel Manufacturing', 2, 278),
(416, 'NAICS', 316, 'Leather and Allied Product Manufacturing', 2, 278),
(427, 'NAICS', 321, 'Wood Product Manufacturing', 2, 278),
(640, 'NAICS', 332, 'Fabricated Metal Product Manufacturing', 2, 278),
(450, 'NAICS', 322, 'Paper Manufacturing', 2, 278),
(471, 'NAICS', 323, 'Printing and Related Support Activities', 2, 278),
(479, 'NAICS', 324, 'Petroleum and Coal Products Manufacturing', 2, 278),
(607, 'NAICS', 331, 'Primary Metal Manufacturing', 2, 278),
(489, 'NAICS', 325, 'Chemical Manufacturing', 2, 278),
(543, 'NAICS', 326, 'Plastics and Rubber Products Manufacturing', 2, 278),
(329, 'NAICS', 3118, 'Bakeries and Tortilla Manufacturing', 3, 279),
(326, 'NAICS', 3117, 'Seafood Product Preparation and Packaging', 3, 279),
(320, 'NAICS', 3116, 'Animal Slaughtering and Processing', 3, 279),
(295, 'NAICS', 3113, 'Sugar and Confectionery Product Manufacturing', 3, 279),
(280, 'NAICS', 3111, 'Animal Food Manufacturing', 3, 279),
(284, 'NAICS', 3112, 'Grain and Oilseed Milling', 3, 279),
(304, 'NAICS', 3114, 'Fruit and Vegetable Preserving and Specialty Food Manufacturing', 3, 279),
(312, 'NAICS', 3115, 'Dairy Product Manufacturing', 3, 279),
(339, 'NAICS', 3119, 'Other Food Manufacturing', 3, 279),
(281, 'NAICS', 31111, 'Animal Food Manufacturing', 4, 280),
(283, 'NAICS', 311119, 'Other Animal Food Manufacturing', 5, 281),
(282, 'NAICS', 311111, 'Dog and Cat Food Manufacturing', 5, 281),
(289, 'NAICS', 31122, 'Starch and Vegetable Fats and Oils Manufacturing', 4, 284),
(285, 'NAICS', 31121, 'Flour Milling and Malt Manufacturing', 4, 284),
(294, 'NAICS', 31123, 'Breakfast Cereal Manufacturing', 4, 284),
(287, 'NAICS', 311212, 'Rice Milling', 5, 285),
(288, 'NAICS', 311213, 'Malt Manufacturing', 5, 285),
(286, 'NAICS', 311211, 'Flour Milling', 5, 285),
(290, 'NAICS', 311221, 'Wet Corn Milling', 5, 289),
(292, 'NAICS', 311225, 'Fats and Oils Refining and Blending', 5, 289),
(291, 'NAICS', 311224, 'Soybean and Other Oilseed Processing', 5, 289),
(293, 'NAICS', 311230, 'Breakfast Cereal Manufacturing', 5, 294),
(300, 'NAICS', 31134, 'Nonchocolate Confectionery Manufacturing', 4, 295),
(301, 'NAICS', 31135, 'Chocolate and Confectionery Manufacturing', 4, 295),
(298, 'NAICS', 311314, 'Cane Sugar Manufacturing', 5, 296),
(297, 'NAICS', 311313, 'Beet Sugar Manufacturing', 5, 296),
(299, 'NAICS', 311340, 'Nonchocolate Confectionery Manufacturing', 5, 300),
(303, 'NAICS', 311352, 'Confectionery Manufacturing from Purchased Chocolate', 5, 301),
(302, 'NAICS', 311351, 'Chocolate and Confectionery Manufacturing from Cacao Beans', 5, 301),
(305, 'NAICS', 31141, 'Frozen Food Manufacturing', 4, 304),
(308, 'NAICS', 31142, 'Fruit and Vegetable Canning, Pickling, and Drying', 4, 304),
(306, 'NAICS', 311411, 'Frozen Fruit, Juice, and Vegetable Manufacturing', 5, 305),
(307, 'NAICS', 311412, 'Frozen Specialty Food Manufacturing', 5, 305),
(311, 'NAICS', 311423, 'Dried and Dehydrated Food Manufacturing', 5, 308),
(309, 'NAICS', 311421, 'Fruit and Vegetable Canning', 5, 308),
(310, 'NAICS', 311422, 'Specialty Canning', 5, 308),
(319, 'NAICS', 31152, 'Ice Cream and Frozen Dessert Manufacturing', 4, 312),
(313, 'NAICS', 31151, 'Dairy Product (except Frozen) Manufacturing', 4, 312),
(317, 'NAICS', 311514, 'Dry, Condensed, and Evaporated Dairy Product Manufacturing', 5, 313),
(316, 'NAICS', 311513, 'Cheese Manufacturing', 5, 313),
(315, 'NAICS', 311512, 'Creamery Butter Manufacturing', 5, 313),
(314, 'NAICS', 311511, 'Fluid Milk Manufacturing', 5, 313),
(318, 'NAICS', 311520, 'Ice Cream and Frozen Dessert Manufacturing', 5, 319),
(321, 'NAICS', 31161, 'Animal Slaughtering and Processing', 4, 320),
(323, 'NAICS', 311612, 'Meat Processed from Carcasses', 5, 321),
(322, 'NAICS', 311611, 'Animal (except Poultry) Slaughtering', 5, 321),
(324, 'NAICS', 311613, 'Rendering and Meat Byproduct Processing', 5, 321),
(325, 'NAICS', 311615, 'Poultry Processing', 5, 321),
(328, 'NAICS', 31171, 'Seafood Product Preparation and Packaging', 4, 326),
(327, 'NAICS', 311710, 'Seafood Product Preparation and Packaging', 5, 328),
(338, 'NAICS', 31183, 'Tortilla Manufacturing', 4, 329),
(330, 'NAICS', 31181, 'Bread and Bakery Product Manufacturing', 4, 329),
(334, 'NAICS', 31182, 'Cookie, Cracker, and Pasta Manufacturing', 4, 329),
(331, 'NAICS', 311811, 'Retail Bakeries', 5, 330),
(332, 'NAICS', 311812, 'Commercial Bakeries', 5, 330),
(333, 'NAICS', 311813, 'Frozen Cakes, Pies, and Other Pastries Manufacturing', 5, 330),
(335, 'NAICS', 311821, 'Cookie and Cracker Manufacturing', 5, 334),
(336, 'NAICS', 311824, 'Dry Pasta, Dough, and Flour Mixes Manufacturing from Purchased Flour', 5, 334),
(337, 'NAICS', 311830, 'Tortilla Manufacturing', 5, 338),
(347, 'NAICS', 31194, 'Seasoning and Dressing Manufacturing', 4, 339),
(340, 'NAICS', 31191, 'Snack Food Manufacturing', 4, 339),
(344, 'NAICS', 31192, 'Coffee and Tea Manufacturing', 4, 339),
(346, 'NAICS', 31193, 'Flavoring Syrup and Concentrate Manufacturing', 4, 339),
(350, 'NAICS', 31199, 'All Other Food Manufacturing', 4, 339),
(341, 'NAICS', 311911, 'Roasted Nuts and Peanut Butter Manufacturing', 5, 340),
(342, 'NAICS', 311919, 'Other Snack Food Manufacturing', 5, 340),
(343, 'NAICS', 311920, 'Coffee and Tea Manufacturing', 5, 344),
(345, 'NAICS', 311930, 'Flavoring Syrup and Concentrate Manufacturing', 5, 346),
(349, 'NAICS', 311942, 'Spice and Extract Manufacturing', 5, 347),
(348, 'NAICS', 311941, 'Mayonnaise, Dressing, and Other Prepared Sauce Manufacturing', 5, 347),
(351, 'NAICS', 311991, 'Perishable Prepared Food Manufacturing', 5, 350),
(352, 'NAICS', 311999, 'All Other Miscellaneous Food Manufacturing', 5, 350),
(354, 'NAICS', 3121, 'Beverage Manufacturing', 3, 353),
(365, 'NAICS', 3122, 'Tobacco Manufacturing', 3, 353),
(364, 'NAICS', 31214, 'Distilleries', 4, 354),
(360, 'NAICS', 31212, 'Breweries', 4, 354),
(355, 'NAICS', 31211, 'Soft Drink and Ice Manufacturing', 4, 354),
(362, 'NAICS', 31213, 'Wineries', 4, 354),
(356, 'NAICS', 312111, 'Soft Drink Manufacturing', 5, 355),
(357, 'NAICS', 312112, 'Bottled Water Manufacturing', 5, 355),
(358, 'NAICS', 312113, 'Ice Manufacturing', 5, 355),
(359, 'NAICS', 312120, 'Breweries', 5, 360),
(361, 'NAICS', 312130, 'Wineries', 5, 362),
(363, 'NAICS', 312140, 'Distilleries', 5, 364),
(367, 'NAICS', 31223, 'Tobacco Manufacturing', 4, 365),
(366, 'NAICS', 312230, 'Tobacco Manufacturing', 5, 367),
(381, 'NAICS', 3133, 'Textile and Fabric Finishing and Fabric Coating Mills', 3, 368),
(369, 'NAICS', 3131, 'Fiber, Yarn, and Thread Mills', 3, 368),
(372, 'NAICS', 3132, 'Fabric Mills', 3, 368),
(371, 'NAICS', 31311, 'Fiber, Yarn, and Thread Mills', 4, 369),
(370, 'NAICS', 313110, 'Fiber, Yarn, and Thread Mills', 5, 371),
(376, 'NAICS', 31322, 'Narrow Fabric Mills and Schiffli Machine Embroidery', 4, 372),
(378, 'NAICS', 31323, 'Nonwoven Fabric Mills', 4, 372),
(374, 'NAICS', 31321, 'Broadwoven Fabric Mills', 4, 372),
(380, 'NAICS', 31324, 'Knit Fabric Mills', 4, 372),
(373, 'NAICS', 313210, 'Broadwoven Fabric Mills', 5, 374),
(375, 'NAICS', 313220, 'Narrow Fabric Mills and Schiffli Machine Embroidery', 5, 376),
(377, 'NAICS', 313230, 'Nonwoven Fabric Mills', 5, 378),
(379, 'NAICS', 313240, 'Knit Fabric Mills', 5, 380),
(385, 'NAICS', 31332, 'Fabric Coating Mills', 4, 381),
(383, 'NAICS', 31331, 'Textile and Fabric Finishing Mills', 4, 381),
(382, 'NAICS', 313310, 'Textile and Fabric Finishing Mills', 5, 383),
(384, 'NAICS', 313320, 'Fabric Coating Mills', 5, 385),
(387, 'NAICS', 3141, 'Textile Furnishings Mills', 3, 386),
(392, 'NAICS', 3149, 'Other Textile Product Mills', 3, 386),
(391, 'NAICS', 31412, 'Curtain and Linen Mills', 4, 387),
(389, 'NAICS', 31411, 'Carpet and Rug Mills', 4, 387),
(388, 'NAICS', 314110, 'Carpet and Rug Mills', 5, 389),
(390, 'NAICS', 314120, 'Curtain and Linen Mills', 5, 391),
(394, 'NAICS', 31491, 'Textile Bag and Canvas Mills', 4, 392),
(395, 'NAICS', 31499, 'All Other Textile Product Mills', 4, 392),
(393, 'NAICS', 314910, 'Textile Bag and Canvas Mills', 5, 394),
(396, 'NAICS', 314994, 'Rope, Cordage, Twine, Tire Cord, and Tire Fabric Mills', 5, 395),
(397, 'NAICS', 314999, 'All Other Miscellaneous Textile Product Mills', 5, 395),
(399, 'NAICS', 3151, 'Apparel Knitting Mills', 3, 398),
(404, 'NAICS', 3152, 'Cut and Sew Apparel Manufacturing', 3, 398),
(413, 'NAICS', 3159, 'Apparel Accessories and Other Apparel Manufacturing', 3, 398),
(403, 'NAICS', 31519, 'Other Apparel Knitting Mills', 4, 399),
(401, 'NAICS', 31511, 'Hosiery and Sock Mills', 4, 399),
(400, 'NAICS', 315110, 'Hosiery and Sock Mills', 5, 401),
(402, 'NAICS', 315190, 'Other Apparel Knitting Mills', 5, 403),
(412, 'NAICS', 31528, 'Other Cut and Sew Apparel Manufacturing', 4, 404),
(406, 'NAICS', 31521, 'Cut and Sew Apparel Contractors', 4, 404),
(408, 'NAICS', 31522, 'Men.s and Boys. Cut and Sew Apparel Manufacturing', 4, 404),
(410, 'NAICS', 31524, 'Women.s, Girls., and Infants. Cut and Sew Apparel Manufacturing', 4, 404),
(405, 'NAICS', 315210, 'Cut and Sew Apparel Contractors', 5, 406),
(407, 'NAICS', 315220, 'Men.s and Boys. Cut and Sew Apparel Manufacturing', 5, 408),
(409, 'NAICS', 315240, 'Women.s, Girls., and Infants. Cut and Sew Apparel Manufacturing', 5, 410),
(411, 'NAICS', 315280, 'Other Cut and Sew Apparel Manufacturing', 5, 412),
(415, 'NAICS', 31599, 'Apparel Accessories and Other Apparel Manufacturing', 4, 413),
(414, 'NAICS', 315990, 'Apparel Accessories and Other Apparel Manufacturing', 5, 415),
(420, 'NAICS', 3162, 'Footwear Manufacturing', 3, 416),
(423, 'NAICS', 3169, 'Other Leather and Allied Product Manufacturing', 3, 416),
(417, 'NAICS', 3161, 'Leather and Hide Tanning and Finishing', 3, 416),
(419, 'NAICS', 31611, 'Leather and Hide Tanning and Finishing', 4, 417),
(418, 'NAICS', 316110, 'Leather and Hide Tanning and Finishing', 5, 419),
(422, 'NAICS', 31621, 'Footwear Manufacturing', 4, 420),
(421, 'NAICS', 316210, 'Footwear Manufacturing', 5, 422),
(424, 'NAICS', 31699, 'Other Leather and Allied Product Manufacturing', 4, 423),
(426, 'NAICS', 316998, 'All Other Leather Good and Allied Product Manufacturing', 5, 424),
(425, 'NAICS', 316992, 'Women''s Handbag and Purse Manufacturing', 5, 424),
(439, 'NAICS', 3219, 'Other Wood Product Manufacturing', 3, 427),
(428, 'NAICS', 3211, 'Sawmills and Wood Preservation', 3, 427),
(432, 'NAICS', 3212, 'Veneer, Plywood, and Engineered Wood Product Manufacturing', 3, 427),
(429, 'NAICS', 32111, 'Sawmills and Wood Preservation', 4, 428),
(430, 'NAICS', 321113, 'Sawmills', 5, 429),
(431, 'NAICS', 321114, 'Wood Preservation', 5, 429),
(433, 'NAICS', 32121, 'Veneer, Plywood, and Engineered Wood Product Manufacturing', 4, 432),
(435, 'NAICS', 321212, 'Softwood Veneer and Plywood Manufacturing', 5, 433),
(434, 'NAICS', 321211, 'Hardwood Veneer and Plywood Manufacturing', 5, 433),
(436, 'NAICS', 321213, 'Engineered Wood Member (except Truss) Manufacturing', 5, 433),
(437, 'NAICS', 321214, 'Truss Manufacturing', 5, 433),
(438, 'NAICS', 321219, 'Reconstituted Wood Product Manufacturing', 5, 433),
(445, 'NAICS', 32192, 'Wood Container and Pallet Manufacturing', 4, 439),
(440, 'NAICS', 32191, 'Millwork', 4, 439),
(446, 'NAICS', 32199, 'All Other Wood Product Manufacturing', 4, 439),
(442, 'NAICS', 321912, 'Cut Stock, Resawing Lumber, and Planing', 5, 440),
(443, 'NAICS', 321918, 'Other Millwork (including Flooring)', 5, 440),
(441, 'NAICS', 321911, 'Wood Window and Door Manufacturing', 5, 440),
(444, 'NAICS', 321920, 'Wood Container and Pallet Manufacturing', 5, 445),
(447, 'NAICS', 321991, 'Manufactured Home (Mobile Home) Manufacturing', 5, 446),
(448, 'NAICS', 321992, 'Prefabricated Wood Building Manufacturing', 5, 446),
(449, 'NAICS', 321999, 'All Other Miscellaneous Wood Product Manufacturing', 5, 446),
(459, 'NAICS', 3222, 'Converted Paper Product Manufacturing', 3, 450),
(451, 'NAICS', 3221, 'Pulp, Paper, and Paperboard Mills', 3, 450),
(454, 'NAICS', 32212, 'Paper Mills', 4, 451),
(453, 'NAICS', 32211, 'Pulp Mills', 4, 451),
(458, 'NAICS', 32213, 'Paperboard Mills', 4, 451),
(452, 'NAICS', 322110, 'Pulp Mills', 5, 453),
(456, 'NAICS', 322122, 'Newsprint Mills', 5, 454),
(455, 'NAICS', 322121, 'Paper (except Newsprint) Mills', 5, 454),
(457, 'NAICS', 322130, 'Paperboard Mills', 5, 458),
(460, 'NAICS', 32221, 'Paperboard Container Manufacturing', 4, 459),
(467, 'NAICS', 32223, 'Stationery Product Manufacturing', 4, 459),
(468, 'NAICS', 32229, 'Other Converted Paper Product Manufacturing', 4, 459),
(465, 'NAICS', 32222, 'Paper Bag and Coated and Treated Paper Manufacturing', 4, 459),
(463, 'NAICS', 322219, 'Other Paperboard Container Manufacturing', 5, 460),
(462, 'NAICS', 322212, 'Folding Paperboard Box Manufacturing', 5, 460),
(461, 'NAICS', 322211, 'Corrugated and Solid Fiber Box Manufacturing', 5, 460),
(464, 'NAICS', 322220, 'Paper Bag and Coated and Treated Paper Manufacturing', 5, 465),
(466, 'NAICS', 322230, 'Stationery Product Manufacturing', 5, 467),
(469, 'NAICS', 322291, 'Sanitary Paper Product Manufacturing', 5, 468),
(470, 'NAICS', 322299, 'All Other Converted Paper Product Manufacturing', 5, 468),
(472, 'NAICS', 3231, 'Printing and Related Support Activities', 3, 471),
(478, 'NAICS', 32312, 'Support Activities for Printing', 4, 472),
(473, 'NAICS', 32311, 'Printing', 4, 472),
(827, 'NAICS', 33593, 'Wiring Device Manufacturing', 4, 820),
(474, 'NAICS', 323111, 'Commercial Printing (except Screen and Books)', 5, 473),
(475, 'NAICS', 323113, 'Commercial Screen Printing', 5, 473),
(476, 'NAICS', 323117, 'Books Printing', 5, 473),
(477, 'NAICS', 323120, 'Support Activities for Printing', 5, 478),
(480, 'NAICS', 3241, 'Petroleum and Coal Products Manufacturing', 3, 479),
(482, 'NAICS', 32411, 'Petroleum Refineries', 4, 480),
(486, 'NAICS', 32419, 'Other Petroleum and Coal Products Manufacturing', 4, 480),
(483, 'NAICS', 32412, 'Asphalt Paving, Roofing, and Saturated Materials Manufacturing', 4, 480),
(481, 'NAICS', 324110, 'Petroleum Refineries', 5, 482),
(485, 'NAICS', 324122, 'Asphalt Shingle and Coating Materials Manufacturing', 5, 483),
(484, 'NAICS', 324121, 'Asphalt Paving Mixture and Block Manufacturing', 5, 483),
(488, 'NAICS', 324199, 'All Other Petroleum and Coal Products Manufacturing', 5, 486),
(487, 'NAICS', 324191, 'Petroleum Lubricating Oil and Grease Manufacturing', 5, 486),
(534, 'NAICS', 3259, 'Other Chemical Product and Preparation Manufacturing', 3, 489),
(522, 'NAICS', 3255, 'Paint, Coating, and Adhesive Manufacturing', 3, 489),
(509, 'NAICS', 3253, 'Pesticide, Fertilizer, and Other Agricultural Chemical Manufacturing', 3, 489),
(516, 'NAICS', 3254, 'Pharmaceutical and Medicine Manufacturing', 3, 489),
(503, 'NAICS', 3252, 'Resin, Synthetic Rubber, and Artificial Synthetic Fibers and Filaments Manufacturing', 3, 489),
(490, 'NAICS', 3251, 'Basic Chemical Manufacturing', 3, 489),
(527, 'NAICS', 3256, 'Soap, Cleaning Compound, and Toilet Preparation Manufacturing', 3, 489),
(492, 'NAICS', 32511, 'Petrochemical Manufacturing', 4, 490),
(494, 'NAICS', 32512, 'Industrial Gas Manufacturing', 4, 490),
(496, 'NAICS', 32513, 'Synthetic Dye and Pigment Manufacturing', 4, 490),
(498, 'NAICS', 32518, 'Other Basic Inorganic Chemical Manufacturing', 4, 490),
(499, 'NAICS', 32519, 'Other Basic Organic Chemical Manufacturing', 4, 490),
(491, 'NAICS', 325110, 'Petrochemical Manufacturing', 5, 492),
(493, 'NAICS', 325120, 'Industrial Gas Manufacturing', 5, 494),
(495, 'NAICS', 325130, 'Synthetic Dye and Pigment Manufacturing', 5, 496),
(497, 'NAICS', 325180, 'Other Basic Inorganic Chemical Manufacturing', 5, 498),
(501, 'NAICS', 325194, 'Cyclic Crude, Intermediate, and Gum and Wood Chemical Manufacturing', 5, 499),
(500, 'NAICS', 325193, 'Ethyl Alcohol Manufacturing', 5, 499),
(502, 'NAICS', 325199, 'All Other Basic Organic Chemical Manufacturing', 5, 499),
(508, 'NAICS', 32522, 'Artificial and Synthetic Fibers and Filaments Manufacturing', 4, 503),
(504, 'NAICS', 32521, 'Resin and Synthetic Rubber Manufacturing', 4, 503),
(506, 'NAICS', 325212, 'Synthetic Rubber Manufacturing', 5, 504),
(505, 'NAICS', 325211, 'Plastics Material and Resin Manufacturing', 5, 504),
(507, 'NAICS', 325220, 'Artificial and Synthetic Fibers and Filaments Manufacturing', 5, 508),
(515, 'NAICS', 32532, 'Pesticide and Other Agricultural Chemical Manufacturing', 4, 509),
(510, 'NAICS', 32531, 'Fertilizer Manufacturing', 4, 509),
(512, 'NAICS', 325312, 'Phosphatic Fertilizer Manufacturing', 5, 510),
(513, 'NAICS', 325314, 'Fertilizer (Mixing Only) Manufacturing', 5, 510),
(511, 'NAICS', 325311, 'Nitrogenous Fertilizer Manufacturing', 5, 510),
(514, 'NAICS', 325320, 'Pesticide and Other Agricultural Chemical Manufacturing', 5, 515),
(517, 'NAICS', 32541, 'Pharmaceutical and Medicine Manufacturing', 4, 516),
(519, 'NAICS', 325412, 'Pharmaceutical Preparation Manufacturing', 5, 517),
(520, 'NAICS', 325413, 'In-Vitro Diagnostic Substance Manufacturing', 5, 517),
(521, 'NAICS', 325414, 'Biological Product (except Diagnostic) Manufacturing', 5, 517),
(518, 'NAICS', 325411, 'Medicinal and Botanical Manufacturing', 5, 517),
(524, 'NAICS', 32551, 'Paint and Coating Manufacturing', 4, 522),
(526, 'NAICS', 32552, 'Adhesive Manufacturing', 4, 522),
(523, 'NAICS', 325510, 'Paint and Coating Manufacturing', 5, 524),
(525, 'NAICS', 325520, 'Adhesive Manufacturing', 5, 526),
(533, 'NAICS', 32562, 'Toilet Preparation Manufacturing', 4, 527),
(528, 'NAICS', 32561, 'Soap and Cleaning Compound Manufacturing', 4, 527),
(530, 'NAICS', 325612, 'Polish and Other Sanitation Good Manufacturing', 5, 528),
(531, 'NAICS', 325613, 'Surface Active Agent Manufacturing', 5, 528),
(529, 'NAICS', 325611, 'Soap and Other Detergent Manufacturing', 5, 528),
(532, 'NAICS', 325620, 'Toilet Preparation Manufacturing', 5, 533),
(539, 'NAICS', 32599, 'All Other Chemical Product and Preparation Manufacturing', 4, 534),
(538, 'NAICS', 32592, 'Explosives Manufacturing', 4, 534),
(536, 'NAICS', 32591, 'Printing Ink Manufacturing', 4, 534),
(535, 'NAICS', 325910, 'Printing Ink Manufacturing', 5, 536),
(537, 'NAICS', 325920, 'Explosives Manufacturing', 5, 538),
(540, 'NAICS', 325991, 'Custom Compounding of Purchased Resins', 5, 539),
(541, 'NAICS', 325992, 'Photographic Film, Paper, Plate, and Chemical Manufacturing', 5, 539),
(542, 'NAICS', 325998, 'All Other Miscellaneous Chemical Product and Preparation Manufacturing', 5, 539),
(563, 'NAICS', 3262, 'Rubber Product Manufacturing', 3, 543),
(544, 'NAICS', 3261, 'Plastics Product Manufacturing', 3, 543),
(549, 'NAICS', 32612, 'Plastics Pipe, Pipe Fitting, and Unlaminated Profile Shape Manufacturing', 4, 544),
(545, 'NAICS', 32611, 'Plastics Packaging Materials and Unlaminated Film and Sheet Manufacturing', 4, 544),
(553, 'NAICS', 32613, 'Laminated Plastics Plate, Sheet (except Packaging), and Shape Manufacturing', 4, 544),
(555, 'NAICS', 32614, 'Polystyrene Foam Product Manufacturing', 4, 544),
(557, 'NAICS', 32615, 'Urethane and Other Foam Product (except Polystyrene) Manufacturing', 4, 544),
(559, 'NAICS', 32616, 'Plastics Bottle Manufacturing', 4, 544),
(560, 'NAICS', 32619, 'Other Plastics Product Manufacturing', 4, 544),
(546, 'NAICS', 326111, 'Plastics Bag and Pouch Manufacturing', 5, 545),
(548, 'NAICS', 326113, 'Unlaminated Plastics Film and Sheet (except Packaging) Manufacturing', 5, 545),
(547, 'NAICS', 326112, 'Plastics Packaging Film and Sheet (including Laminated) Manufacturing', 5, 545),
(551, 'NAICS', 326122, 'Plastics Pipe and Pipe Fitting Manufacturing', 5, 549),
(550, 'NAICS', 326121, 'Unlaminated Plastics Profile Shape Manufacturing', 5, 549),
(552, 'NAICS', 326130, 'Laminated Plastics Plate, Sheet (except Packaging), and Shape Manufacturing', 5, 553),
(554, 'NAICS', 326140, 'Polystyrene Foam Product Manufacturing', 5, 555),
(556, 'NAICS', 326150, 'Urethane and Other Foam Product (except Polystyrene) Manufacturing', 5, 557),
(558, 'NAICS', 326160, 'Plastics Bottle Manufacturing', 5, 559),
(562, 'NAICS', 326199, 'All Other Plastics Product Manufacturing', 5, 560),
(561, 'NAICS', 326191, 'Plastics Plumbing Fixture Manufacturing', 5, 560),
(568, 'NAICS', 32622, 'Rubber and Plastics Hoses and Belting Manufacturing', 4, 563),
(569, 'NAICS', 32629, 'Other Rubber Product Manufacturing', 4, 563),
(564, 'NAICS', 32621, 'Tire Manufacturing', 4, 563),
(565, 'NAICS', 326211, 'Tire Manufacturing (except Retreading)', 5, 564),
(566, 'NAICS', 326212, 'Tire Retreading', 5, 564),
(567, 'NAICS', 326220, 'Rubber and Plastics Hoses and Belting Manufacturing', 5, 568),
(571, 'NAICS', 326299, 'All Other Rubber Product Manufacturing', 5, 569),
(570, 'NAICS', 326291, 'Rubber Product Manufacturing for Mechanical Use', 5, 569),
(578, 'NAICS', 3272, 'Glass and Glass Product Manufacturing', 3, 572),
(594, 'NAICS', 3274, 'Lime and Gypsum Product Manufacturing', 3, 572),
(584, 'NAICS', 3273, 'Cement and Concrete Product Manufacturing', 3, 572),
(599, 'NAICS', 3279, 'Other Nonmetallic Mineral Product Manufacturing', 3, 572),
(573, 'NAICS', 3271, 'Clay Product and Refractory Manufacturing', 3, 572),
(577, 'NAICS', 32712, 'Clay Building Material and Refractories Manufacturing', 4, 573),
(575, 'NAICS', 32711, 'Pottery, Ceramics, and Plumbing Fixture Manufacturing', 4, 573),
(574, 'NAICS', 327110, 'Pottery, Ceramics, and Plumbing Fixture Manufacturing', 5, 575),
(576, 'NAICS', 327120, 'Clay Building Material and Refractories Manufacturing', 5, 577),
(579, 'NAICS', 32721, 'Glass and Glass Product Manufacturing', 4, 578),
(582, 'NAICS', 327213, 'Glass Container Manufacturing', 5, 579),
(583, 'NAICS', 327215, 'Glass Product Manufacturing Made of Purchased Glass', 5, 579),
(580, 'NAICS', 327211, 'Flat Glass Manufacturing', 5, 579),
(645, 'NAICS', 332114, 'Custom Roll Forming', 5, 642),
(581, 'NAICS', 327212, 'Other Pressed and Blown Glass and Glassware Manufacturing', 5, 579),
(588, 'NAICS', 32732, 'Ready-Mix Concrete Manufacturing', 4, 584),
(586, 'NAICS', 32731, 'Cement Manufacturing', 4, 584),
(589, 'NAICS', 32733, 'Concrete Pipe, Brick, and Block Manufacturing', 4, 584),
(593, 'NAICS', 32739, 'Other Concrete Product Manufacturing', 4, 584),
(585, 'NAICS', 327310, 'Cement Manufacturing', 5, 586),
(587, 'NAICS', 327320, 'Ready-Mix Concrete Manufacturing', 5, 588),
(590, 'NAICS', 327331, 'Concrete Block and Brick Manufacturing', 5, 589),
(591, 'NAICS', 327332, 'Concrete Pipe Manufacturing', 5, 589),
(592, 'NAICS', 327390, 'Other Concrete Product Manufacturing', 5, 593),
(596, 'NAICS', 32741, 'Lime Manufacturing', 4, 594),
(598, 'NAICS', 32742, 'Gypsum Product Manufacturing', 4, 594),
(595, 'NAICS', 327410, 'Lime Manufacturing', 5, 596),
(597, 'NAICS', 327420, 'Gypsum Product Manufacturing', 5, 598),
(602, 'NAICS', 32799, 'All Other Nonmetallic Mineral Product Manufacturing', 4, 599),
(601, 'NAICS', 32791, 'Abrasive Product Manufacturing', 4, 599),
(600, 'NAICS', 327910, 'Abrasive Product Manufacturing', 5, 601),
(603, 'NAICS', 327991, 'Cut Stone and Stone Product Manufacturing', 5, 602),
(604, 'NAICS', 327992, 'Ground or Treated Mineral and Earth Manufacturing', 5, 602),
(606, 'NAICS', 327999, 'All Other Miscellaneous Nonmetallic Mineral Product Manufacturing', 5, 602),
(605, 'NAICS', 327993, 'Mineral Wool Manufacturing', 5, 602),
(623, 'NAICS', 3314, 'Nonferrous Metal (except Aluminum) Production and Processing', 3, 607),
(611, 'NAICS', 3312, 'Steel Product Manufacturing from Purchased Steel', 3, 607),
(608, 'NAICS', 3311, 'Iron and Steel Mills and Ferroalloy Manufacturing', 3, 607),
(631, 'NAICS', 3315, 'Foundries', 3, 607),
(617, 'NAICS', 3313, 'Alumina and Aluminum Production and Processing', 3, 607),
(610, 'NAICS', 33111, 'Iron and Steel Mills and Ferroalloy Manufacturing', 4, 608),
(609, 'NAICS', 331110, 'Iron and Steel Mills and Ferroalloy Manufacturing', 5, 610),
(614, 'NAICS', 33122, 'Rolling and Drawing of Purchased Steel', 4, 611),
(613, 'NAICS', 33121, 'Iron and Steel Pipe and Tube Manufacturing from Purchased Steel', 4, 611),
(612, 'NAICS', 331210, 'Iron and Steel Pipe and Tube Manufacturing from Purchased Steel', 5, 613),
(616, 'NAICS', 331222, 'Steel Wire Drawing', 5, 614),
(615, 'NAICS', 331221, 'Rolled Steel Shape Manufacturing', 5, 614),
(618, 'NAICS', 33131, 'Alumina and Aluminum Production and Processing', 4, 617),
(622, 'NAICS', 331318, 'Other Aluminum Rolling, Drawing, and Extruding', 5, 618),
(619, 'NAICS', 331313, 'Alumina Refining and Primary Aluminum Production', 5, 618),
(620, 'NAICS', 331314, 'Secondary Smelting and Alloying of Aluminum', 5, 618),
(621, 'NAICS', 331315, 'Aluminum Sheet, Plate, and Foil Manufacturing', 5, 618),
(627, 'NAICS', 33142, 'Copper Rolling, Drawing, Extruding, and Alloying', 4, 623),
(628, 'NAICS', 33149, 'Nonferrous Metal (except Copper and Aluminum) Rolling, Drawing, Extruding, and Alloying', 4, 623),
(625, 'NAICS', 33141, 'Nonferrous Metal (except Aluminum) Smelting and Refining', 4, 623),
(624, 'NAICS', 331410, 'Nonferrous Metal (except Aluminum) Smelting and Refining', 5, 625),
(626, 'NAICS', 331420, 'Copper Rolling, Drawing, Extruding, and Alloying', 5, 627),
(630, 'NAICS', 331492, 'Secondary Smelting, Refining, and Alloying of Nonferrous Metal (except Copper and Aluminum)', 5, 628),
(629, 'NAICS', 331491, 'Nonferrous Metal (except Copper and Aluminum) Rolling, Drawing, and Extruding', 5, 628),
(632, 'NAICS', 33151, 'Ferrous Metal Foundries', 4, 631),
(636, 'NAICS', 33152, 'Nonferrous Metal Foundries', 4, 631),
(633, 'NAICS', 331511, 'Iron Foundries', 5, 632),
(635, 'NAICS', 331513, 'Steel Foundries (except Investment)', 5, 632),
(634, 'NAICS', 331512, 'Steel Investment Foundries', 5, 632),
(639, 'NAICS', 331529, 'Other Nonferrous Metal Foundries (except Die-Casting)', 5, 636),
(637, 'NAICS', 331523, 'Nonferrous Metal Die-Casting Foundries', 5, 636),
(638, 'NAICS', 331524, 'Aluminum Foundries (except Die-Casting)', 5, 636),
(672, 'NAICS', 3326, 'Spring and Wire Product Manufacturing', 3, 640),
(687, 'NAICS', 3329, 'Other Fabricated Metal Product Manufacturing', 3, 640),
(669, 'NAICS', 3325, 'Hardware Manufacturing', 3, 640),
(641, 'NAICS', 3321, 'Forging and Stamping', 3, 640),
(648, 'NAICS', 3322, 'Cutlery and Handtool Manufacturing', 3, 640),
(652, 'NAICS', 3323, 'Architectural and Structural Metals Manufacturing', 3, 640),
(661, 'NAICS', 3324, 'Boiler, Tank, and Shipping Container Manufacturing', 3, 640),
(676, 'NAICS', 3327, 'Machine Shops, Turned Product, and Screw, Nut, and Bolt Manufacturing', 3, 640),
(682, 'NAICS', 3328, 'Coating, Engraving, Heat Treating, and Allied Activities', 3, 640),
(642, 'NAICS', 33211, 'Forging and Stamping', 4, 641),
(647, 'NAICS', 332119, 'Metal Crown, Closure, and Other Metal Stamping (except Automotive)', 5, 642),
(643, 'NAICS', 332111, 'Iron and Steel Forging', 5, 642),
(644, 'NAICS', 332112, 'Nonferrous Forging', 5, 642),
(646, 'NAICS', 332117, 'Powder Metallurgy Part Manufacturing', 5, 642),
(649, 'NAICS', 33221, 'Cutlery and Handtool Manufacturing', 4, 648),
(651, 'NAICS', 332216, 'Saw Blade and Handtool Manufacturing', 5, 649),
(650, 'NAICS', 332215, 'Metal Kitchen Cookware, Utensil, Cutlery, and Flatware (except Precious) Manufacturing', 5, 649),
(657, 'NAICS', 33232, 'Ornamental and Architectural Metal Products Manufacturing', 4, 652),
(653, 'NAICS', 33231, 'Plate Work and Fabricated Structural Product Manufacturing', 4, 652),
(656, 'NAICS', 332313, 'Plate Work Manufacturing', 5, 653),
(654, 'NAICS', 332311, 'Prefabricated Metal Building and Component Manufacturing', 5, 653),
(655, 'NAICS', 332312, 'Fabricated Structural Metal Manufacturing', 5, 653),
(660, 'NAICS', 332323, 'Ornamental and Architectural Metal Work Manufacturing', 5, 657),
(658, 'NAICS', 332321, 'Metal Window and Door Manufacturing', 5, 657),
(659, 'NAICS', 332322, 'Sheet Metal Work Manufacturing', 5, 657),
(665, 'NAICS', 33242, 'Metal Tank (Heavy Gauge) Manufacturing', 4, 661),
(663, 'NAICS', 33241, 'Power Boiler and Heat Exchanger Manufacturing', 4, 661),
(666, 'NAICS', 33243, 'Metal Can, Box, and Other Metal Container (Light Gauge) Manufacturing', 4, 661),
(662, 'NAICS', 332410, 'Power Boiler and Heat Exchanger Manufacturing', 5, 663),
(664, 'NAICS', 332420, 'Metal Tank (Heavy Gauge) Manufacturing', 5, 665),
(667, 'NAICS', 332431, 'Metal Can Manufacturing', 5, 666),
(668, 'NAICS', 332439, 'Other Metal Container Manufacturing', 5, 666),
(671, 'NAICS', 33251, 'Hardware Manufacturing', 4, 669),
(670, 'NAICS', 332510, 'Hardware Manufacturing', 5, 671),
(673, 'NAICS', 33261, 'Spring and Wire Product Manufacturing', 4, 672),
(674, 'NAICS', 332613, 'Spring Manufacturing', 5, 673),
(675, 'NAICS', 332618, 'Other Fabricated Wire Product Manufacturing', 5, 673),
(678, 'NAICS', 33271, 'Machine Shops', 4, 676),
(679, 'NAICS', 33272, 'Turned Product and Screw, Nut, and Bolt Manufacturing', 4, 676),
(677, 'NAICS', 332710, 'Machine Shops', 5, 678),
(680, 'NAICS', 332721, 'Precision Turned Product Manufacturing', 5, 679),
(681, 'NAICS', 332722, 'Bolt, Nut, Screw, Rivet, and Washer Manufacturing', 5, 679),
(683, 'NAICS', 33281, 'Coating, Engraving, Heat Treating, and Allied Activities', 4, 682),
(685, 'NAICS', 332812, 'Metal Coating, Engraving (except Jewelry and Silverware), and Allied Services to Manufacturers', 5, 683),
(684, 'NAICS', 332811, 'Metal Heat Treating', 5, 683),
(686, 'NAICS', 332813, 'Electroplating, Plating, Polishing, Anodizing, and Coloring', 5, 683),
(688, 'NAICS', 33291, 'Metal Valve Manufacturing', 4, 687),
(693, 'NAICS', 33299, 'All Other Fabricated Metal Product Manufacturing', 4, 687),
(689, 'NAICS', 332911, 'Industrial Valve Manufacturing', 5, 688),
(692, 'NAICS', 332919, 'Other Metal Valve and Pipe Fitting Manufacturing', 5, 688),
(691, 'NAICS', 332913, 'Plumbing Fixture Fitting and Trim Manufacturing', 5, 688),
(690, 'NAICS', 332912, 'Fluid Power Valve and Hose Fitting Manufacturing', 5, 688),
(694, 'NAICS', 332991, 'Ball and Roller Bearing Manufacturing', 5, 693),
(697, 'NAICS', 332994, 'Small Arms, Ordnance, and Ordnance Accessories Manufacturing', 5, 693),
(698, 'NAICS', 332996, 'Fabricated Pipe and Pipe Fitting Manufacturing', 5, 693),
(699, 'NAICS', 332999, 'All Other Miscellaneous Fabricated Metal Product Manufacturing', 5, 693),
(696, 'NAICS', 332993, 'Ammunition (except Small Arms) Manufacturing', 5, 693),
(695, 'NAICS', 332992, 'Small Arms Ammunition Manufacturing', 5, 693),
(727, 'NAICS', 3335, 'Metalworking Machinery Manufacturing', 3, 700),
(701, 'NAICS', 3331, 'Agriculture, Construction, and Mining Machinery Manufacturing', 3, 700),
(710, 'NAICS', 3332, 'Industrial Machinery Manufacturing', 3, 700),
(722, 'NAICS', 3334, 'Ventilation, Heating, Air-Conditioning, and Commercial Refrigeration Equipment Manufacturing', 3, 700),
(734, 'NAICS', 3336, 'Engine, Turbine, and Power Transmission Equipment Manufacturing', 3, 700),
(717, 'NAICS', 3333, 'Commercial and Service Industry Machinery Manufacturing', 3, 700),
(740, 'NAICS', 3339, 'Other General Purpose Machinery Manufacturing', 3, 700),
(702, 'NAICS', 33311, 'Agricultural Implement Manufacturing', 4, 701),
(706, 'NAICS', 33312, 'Construction Machinery Manufacturing', 4, 701),
(707, 'NAICS', 33313, 'Mining and Oil and Gas Field Machinery Manufacturing', 4, 701),
(704, 'NAICS', 333112, 'Lawn and Garden Tractor and Home Lawn and Garden Equipment Manufacturing', 5, 702),
(703, 'NAICS', 333111, 'Farm Machinery and Equipment Manufacturing', 5, 702),
(705, 'NAICS', 333120, 'Construction Machinery Manufacturing', 5, 706),
(708, 'NAICS', 333131, 'Mining Machinery and Equipment Manufacturing', 5, 707),
(709, 'NAICS', 333132, 'Oil and Gas Field Machinery and Equipment Manufacturing', 5, 707),
(711, 'NAICS', 33324, 'Industrial Machinery Manufacturing', 4, 710),
(712, 'NAICS', 333241, 'Food Product Machinery Manufacturing', 5, 711),
(713, 'NAICS', 333242, 'Semiconductor Machinery Manufacturing', 5, 711),
(714, 'NAICS', 333243, 'Sawmill, Woodworking, and Paper Machinery Manufacturing', 5, 711),
(715, 'NAICS', 333244, 'Printing Machinery and Equipment Manufacturing', 5, 711),
(716, 'NAICS', 333249, 'Other Industrial Machinery Manufacturing', 5, 711),
(718, 'NAICS', 33331, 'Commercial and Service Industry Machinery Manufacturing', 4, 717),
(720, 'NAICS', 333316, 'Photographic and Photocopying Equipment Manufacturing', 5, 718),
(721, 'NAICS', 333318, 'Other Commercial and Service Industry Machinery Manufacturing', 5, 718),
(719, 'NAICS', 333314, 'Optical Instrument and Lens Manufacturing', 5, 718),
(723, 'NAICS', 33341, 'Ventilation, Heating, Air-Conditioning, and Commercial Refrigeration Equipment Manufacturing', 4, 722),
(725, 'NAICS', 333414, 'Heating Equipment (except Warm Air Furnaces) Manufacturing', 5, 723),
(724, 'NAICS', 333413, 'Industrial and Commercial Fan and Blower and Air Purification Equipment Manufacturing', 5, 723),
(726, 'NAICS', 333415, 'Air-Conditioning and Warm Air Heating Equipment and Commercial and Industrial Refrigeration Equipment Manufacturing', 5, 723),
(728, 'NAICS', 33351, 'Metalworking Machinery Manufacturing', 4, 727),
(732, 'NAICS', 333517, 'Machine Tool Manufacturing', 5, 728),
(733, 'NAICS', 333519, 'Rolling Mill and Other Metalworking Machinery Manufacturing', 5, 728),
(730, 'NAICS', 333514, 'Special Die and Tool, Die Set, Jig, and Fixture Manufacturing', 5, 728),
(731, 'NAICS', 333515, 'Cutting Tool and Machine Tool Accessory Manufacturing', 5, 728),
(729, 'NAICS', 333511, 'Industrial Mold Manufacturing', 5, 728),
(735, 'NAICS', 33361, 'Engine, Turbine, and Power Transmission Equipment Manufacturing', 4, 734),
(736, 'NAICS', 333611, 'Turbine and Turbine Generator Set Units Manufacturing', 5, 735),
(739, 'NAICS', 333618, 'Other Engine Equipment Manufacturing', 5, 735),
(737, 'NAICS', 333612, 'Speed Changer, Industrial High-Speed Drive, and Gear Manufacturing', 5, 735),
(738, 'NAICS', 333613, 'Mechanical Power Transmission Equipment Manufacturing', 5, 735),
(745, 'NAICS', 33392, 'Material Handling Equipment Manufacturing', 4, 740),
(750, 'NAICS', 33399, 'All Other General Purpose Machinery Manufacturing', 4, 740),
(741, 'NAICS', 33391, 'Pump and Compressor Manufacturing', 4, 740),
(742, 'NAICS', 333911, 'Pump and Pumping Equipment Manufacturing', 5, 741),
(743, 'NAICS', 333912, 'Air and Gas Compressor Manufacturing', 5, 741),
(744, 'NAICS', 333913, 'Measuring and Dispensing Pump Manufacturing', 5, 741),
(746, 'NAICS', 333921, 'Elevator and Moving Stairway Manufacturing', 5, 745),
(748, 'NAICS', 333923, 'Overhead Traveling Crane, Hoist, and Monorail System Manufacturing', 5, 745),
(749, 'NAICS', 333924, 'Industrial Truck, Tractor, Trailer, and Stacker Machinery Manufacturing', 5, 745),
(747, 'NAICS', 333922, 'Conveyor and Conveying Equipment Manufacturing', 5, 745),
(754, 'NAICS', 333994, 'Industrial Process Furnace and Oven Manufacturing', 5, 750),
(751, 'NAICS', 333991, 'Power-Driven Handtool Manufacturing', 5, 750),
(752, 'NAICS', 333992, 'Welding and Soldering Equipment Manufacturing', 5, 750),
(753, 'NAICS', 333993, 'Packaging Machinery Manufacturing', 5, 750),
(755, 'NAICS', 333995, 'Fluid Power Cylinder and Actuator Manufacturing', 5, 750),
(756, 'NAICS', 333996, 'Fluid Power Pump and Motor Manufacturing', 5, 750),
(757, 'NAICS', 333997, 'Scale and Balance Manufacturing', 5, 750),
(758, 'NAICS', 333999, 'All Other Miscellaneous General Purpose Machinery Manufacturing', 5, 750),
(794, 'NAICS', 3346, 'Manufacturing and Reproducing Magnetic and Optical Media', 3, 759),
(775, 'NAICS', 3344, 'Semiconductor and Other Electronic Component Manufacturing', 3, 759),
(772, 'NAICS', 3343, 'Audio and Video Equipment Manufacturing', 3, 759),
(783, 'NAICS', 3345, 'Navigational, Measuring, Electromedical, and Control Instruments Manufacturing', 3, 759),
(765, 'NAICS', 3342, 'Communications Equipment Manufacturing', 3, 759),
(760, 'NAICS', 3341, 'Computer and Peripheral Equipment Manufacturing', 3, 759),
(761, 'NAICS', 33411, 'Computer and Peripheral Equipment Manufacturing', 4, 760),
(763, 'NAICS', 334112, 'Computer Storage Device Manufacturing', 5, 761),
(762, 'NAICS', 334111, 'Electronic Computer Manufacturing', 5, 761),
(764, 'NAICS', 334118, 'Computer Terminal and Other Computer Peripheral Equipment Manufacturing', 5, 761),
(767, 'NAICS', 33421, 'Telephone Apparatus Manufacturing', 4, 765),
(769, 'NAICS', 33422, 'Radio and Television Broadcasting and Wireless Communications Equipment Manufacturing', 4, 765),
(771, 'NAICS', 33429, 'Other Communications Equipment Manufacturing', 4, 765),
(766, 'NAICS', 334210, 'Telephone Apparatus Manufacturing', 5, 767),
(768, 'NAICS', 334220, 'Radio and Television Broadcasting and Wireless Communications Equipment Manufacturing', 5, 769),
(770, 'NAICS', 334290, 'Other Communications Equipment Manufacturing', 5, 771),
(774, 'NAICS', 33431, 'Audio and Video Equipment Manufacturing', 4, 772),
(773, 'NAICS', 334310, 'Audio and Video Equipment Manufacturing', 5, 774),
(776, 'NAICS', 33441, 'Semiconductor and Other Electronic Component Manufacturing', 4, 775),
(780, 'NAICS', 334417, 'Electronic Connector Manufacturing', 5, 776),
(779, 'NAICS', 334416, 'Capacitor, Resistor, Coil, Transformer, and Other Inductor Manufacturing', 5, 776),
(781, 'NAICS', 334418, 'Printed Circuit Assembly (Electronic Assembly) Manufacturing', 5, 776),
(777, 'NAICS', 334412, 'Bare Printed Circuit Board Manufacturing', 5, 776),
(778, 'NAICS', 334413, 'Semiconductor and Related Device Manufacturing', 5, 776),
(782, 'NAICS', 334419, 'Other Electronic Component Manufacturing', 5, 776),
(785, 'NAICS', 33451, 'Navigational, Measuring, Electromedical, and Control Instruments Manufacturing', 4, 783),
(792, 'NAICS', 334517, 'Irradiation Apparatus Manufacturing', 5, 785),
(790, 'NAICS', 334515, 'Instrument Manufacturing for Measuring and Testing Electricity and Electrical Signals', 5, 785),
(789, 'NAICS', 334514, 'Totalizing Fluid Meter and Counting Device Manufacturing', 5, 785),
(788, 'NAICS', 334513, 'Instruments and Related Products Manufacturing for Measuring, Displaying, and Controlling Industrial Process Variables', 5, 785),
(787, 'NAICS', 334512, 'Automatic Environmental Control Manufacturing for Residential, Commercial, and Appliance Use', 5, 785),
(786, 'NAICS', 334511, 'Search, Detection, Navigation, Guidance, Aeronautical, and Nautical System and Instrument Manufacturing', 5, 785),
(784, 'NAICS', 334510, 'Electromedical and Electrotherapeutic Apparatus Manufacturing', 5, 785),
(793, 'NAICS', 334519, 'Other Measuring and Controlling Device Manufacturing', 5, 785),
(791, 'NAICS', 334516, 'Analytical Laboratory Instrument Manufacturing', 5, 785),
(795, 'NAICS', 33461, 'Manufacturing and Reproducing Magnetic and Optical Media', 4, 794),
(797, 'NAICS', 334614, 'Software and Other Prerecorded Compact Disc, Tape, and Record Reproducing', 5, 795),
(796, 'NAICS', 334613, 'Blank Magnetic and Optical Recording Media Manufacturing', 5, 795),
(820, 'NAICS', 3359, 'Other Electrical Equipment and Component Manufacturing', 3, 798),
(799, 'NAICS', 3351, 'Electric Lighting Equipment Manufacturing', 3, 798),
(814, 'NAICS', 3353, 'Electrical Equipment Manufacturing', 3, 798),
(806, 'NAICS', 3352, 'Household Appliance Manufacturing', 3, 798),
(801, 'NAICS', 33511, 'Electric Lamp Bulb and Part Manufacturing', 4, 799),
(802, 'NAICS', 33512, 'Lighting Fixture Manufacturing', 4, 799),
(800, 'NAICS', 335110, 'Electric Lamp Bulb and Part Manufacturing', 5, 801),
(804, 'NAICS', 335122, 'Commercial, Industrial, and Institutional Electric Lighting Fixture Manufacturing', 5, 802),
(803, 'NAICS', 335121, 'Residential Electric Lighting Fixture Manufacturing', 5, 802),
(805, 'NAICS', 335129, 'Other Lighting Equipment Manufacturing', 5, 802),
(809, 'NAICS', 33522, 'Major Appliance Manufacturing', 4, 806),
(808, 'NAICS', 33521, 'Small Electrical Appliance Manufacturing', 4, 806),
(807, 'NAICS', 335210, 'Small Electrical Appliance Manufacturing', 5, 808),
(810, 'NAICS', 335221, 'Household Cooking Appliance Manufacturing', 5, 809),
(813, 'NAICS', 335228, 'Other Major Household Appliance Manufacturing', 5, 809),
(812, 'NAICS', 335224, 'Household Laundry Equipment Manufacturing', 5, 809),
(811, 'NAICS', 335222, 'Household Refrigerator and Home Freezer Manufacturing', 5, 809),
(815, 'NAICS', 33531, 'Electrical Equipment Manufacturing', 4, 814),
(816, 'NAICS', 335311, 'Power, Distribution, and Specialty Transformer Manufacturing', 5, 815),
(817, 'NAICS', 335312, 'Motor and Generator Manufacturing', 5, 815),
(819, 'NAICS', 335314, 'Relay and Industrial Control Manufacturing', 5, 815),
(818, 'NAICS', 335313, 'Switchgear and Switchboard Apparatus Manufacturing', 5, 815),
(824, 'NAICS', 33592, 'Communication and Energy Wire and Cable Manufacturing', 4, 820),
(830, 'NAICS', 33599, 'All Other Electrical Equipment and Component Manufacturing', 4, 820),
(821, 'NAICS', 33591, 'Battery Manufacturing', 4, 820),
(823, 'NAICS', 335912, 'Primary Battery Manufacturing', 5, 821),
(822, 'NAICS', 335911, 'Storage Battery Manufacturing', 5, 821),
(825, 'NAICS', 335921, 'Fiber Optic Cable Manufacturing', 5, 824),
(826, 'NAICS', 335929, 'Other Communication and Energy Wire Manufacturing', 5, 824),
(828, 'NAICS', 335931, 'Current-Carrying Wiring Device Manufacturing', 5, 827),
(829, 'NAICS', 335932, 'Noncurrent-Carrying Wiring Device Manufacturing', 5, 827),
(831, 'NAICS', 335991, 'Carbon and Graphite Product Manufacturing', 5, 830),
(832, 'NAICS', 335999, 'All Other Miscellaneous Electrical Equipment and Component Manufacturing', 5, 830),
(846, 'NAICS', 3363, 'Motor Vehicle Parts Manufacturing', 3, 833),
(863, 'NAICS', 3364, 'Aerospace Product and Parts Manufacturing', 3, 833),
(874, 'NAICS', 3366, 'Ship and Boat Building', 3, 833),
(834, 'NAICS', 3361, 'Motor Vehicle Manufacturing', 3, 833),
(878, 'NAICS', 3369, 'Other Transportation Equipment Manufacturing', 3, 833),
(840, 'NAICS', 3362, 'Motor Vehicle Body and Trailer Manufacturing', 3, 833),
(871, 'NAICS', 3365, 'Railroad Rolling Stock Manufacturing', 3, 833),
(835, 'NAICS', 33611, 'Automobile and Light Duty Motor Vehicle Manufacturing', 4, 834),
(839, 'NAICS', 33612, 'Heavy Duty Truck Manufacturing', 4, 834),
(837, 'NAICS', 336112, 'Light Truck and Utility Vehicle Manufacturing', 5, 835),
(836, 'NAICS', 336111, 'Automobile Manufacturing', 5, 835),
(838, 'NAICS', 336120, 'Heavy Duty Truck Manufacturing', 5, 839),
(841, 'NAICS', 33621, 'Motor Vehicle Body and Trailer Manufacturing', 4, 840),
(843, 'NAICS', 336212, 'Truck Trailer Manufacturing', 5, 841),
(845, 'NAICS', 336214, 'Travel Trailer and Camper Manufacturing', 5, 841),
(844, 'NAICS', 336213, 'Motor Home Manufacturing', 5, 841),
(842, 'NAICS', 336211, 'Motor Vehicle Body Manufacturing', 5, 841),
(856, 'NAICS', 33635, 'Motor Vehicle Transmission and Power Train Parts Manufacturing', 4, 846),
(848, 'NAICS', 33631, 'Motor Vehicle Gasoline Engine and Engine Parts Manufacturing', 4, 846),
(862, 'NAICS', 33639, 'Other Motor Vehicle Parts Manufacturing', 4, 846),
(850, 'NAICS', 33632, 'Motor Vehicle Electrical and Electronic Equipment Manufacturing', 4, 846),
(860, 'NAICS', 33637, 'Motor Vehicle Metal Stamping', 4, 846),
(852, 'NAICS', 33633, 'Motor Vehicle Steering and Suspension Components (except Spring) Manufacturing', 4, 846),
(858, 'NAICS', 33636, 'Motor Vehicle Seating and Interior Trim Manufacturing', 4, 846),
(854, 'NAICS', 33634, 'Motor Vehicle Brake System Manufacturing', 4, 846),
(847, 'NAICS', 336310, 'Motor Vehicle Gasoline Engine and Engine Parts Manufacturing', 5, 848),
(849, 'NAICS', 336320, 'Motor Vehicle Electrical and Electronic Equipment Manufacturing', 5, 850),
(851, 'NAICS', 336330, 'Motor Vehicle Steering and Suspension Components (except Spring) Manufacturing', 5, 852),
(853, 'NAICS', 336340, 'Motor Vehicle Brake System Manufacturing', 5, 854),
(855, 'NAICS', 336350, 'Motor Vehicle Transmission and Power Train Parts Manufacturing', 5, 856),
(857, 'NAICS', 336360, 'Motor Vehicle Seating and Interior Trim Manufacturing', 5, 858),
(859, 'NAICS', 336370, 'Motor Vehicle Metal Stamping', 5, 860),
(861, 'NAICS', 336390, 'Other Motor Vehicle Parts Manufacturing', 5, 862),
(864, 'NAICS', 33641, 'Aerospace Product and Parts Manufacturing', 4, 863),
(865, 'NAICS', 336411, 'Aircraft Manufacturing', 5, 864),
(869, 'NAICS', 336415, 'Guided Missile and Space Vehicle Propulsion Unit and Propulsion Unit Parts Manufacturing', 5, 864),
(870, 'NAICS', 336419, 'Other Guided Missile and Space Vehicle Parts and Auxiliary Equipment Manufacturing', 5, 864),
(867, 'NAICS', 336413, 'Other Aircraft Parts and Auxiliary Equipment Manufacturing', 5, 864),
(866, 'NAICS', 336412, 'Aircraft Engine and Engine Parts Manufacturing', 5, 864),
(868, 'NAICS', 336414, 'Guided Missile and Space Vehicle Manufacturing', 5, 864),
(873, 'NAICS', 33651, 'Railroad Rolling Stock Manufacturing', 4, 871),
(872, 'NAICS', 336510, 'Railroad Rolling Stock Manufacturing', 5, 873),
(875, 'NAICS', 33661, 'Ship and Boat Building', 4, 874),
(876, 'NAICS', 336611, 'Ship Building and Repairing', 5, 875),
(877, 'NAICS', 336612, 'Boat Building', 5, 875),
(879, 'NAICS', 33699, 'Other Transportation Equipment Manufacturing', 4, 878),
(882, 'NAICS', 336999, 'All Other Transportation Equipment Manufacturing', 5, 879),
(881, 'NAICS', 336992, 'Military Armored Vehicle, Tank, and Tank Component Manufacturing', 5, 879),
(880, 'NAICS', 336991, 'Motorcycle, Bicycle, and Parts Manufacturing', 5, 879),
(884, 'NAICS', 3371, 'Household and Institutional Furniture and Kitchen Cabinet Manufacturing', 3, 883),
(893, 'NAICS', 3372, 'Office Furniture (including Fixtures) Manufacturing', 3, 883),
(899, 'NAICS', 3379, 'Other Furniture Related Product Manufacturing', 3, 883),
(886, 'NAICS', 33711, 'Wood Kitchen Cabinet and Countertop Manufacturing', 4, 884),
(887, 'NAICS', 33712, 'Household and Institutional Furniture Manufacturing', 4, 884),
(885, 'NAICS', 337110, 'Wood Kitchen Cabinet and Countertop Manufacturing', 5, 886),
(892, 'NAICS', 337127, 'Institutional Furniture Manufacturing', 5, 887),
(889, 'NAICS', 337122, 'Nonupholstered Wood Household Furniture Manufacturing', 5, 887),
(888, 'NAICS', 337121, 'Upholstered Household Furniture Manufacturing', 5, 887),
(890, 'NAICS', 337124, 'Metal Household Furniture Manufacturing', 5, 887),
(891, 'NAICS', 337125, 'Household Furniture (except Wood and Metal) Manufacturing', 5, 887),
(894, 'NAICS', 33721, 'Office Furniture (including Fixtures) Manufacturing', 4, 893),
(898, 'NAICS', 337215, 'Showcase, Partition, Shelving, and Locker Manufacturing', 5, 894),
(895, 'NAICS', 337211, 'Wood Office Furniture Manufacturing', 5, 894),
(896, 'NAICS', 337212, 'Custom Architectural Woodwork and Millwork Manufacturing', 5, 894),
(897, 'NAICS', 337214, 'Office Furniture (except Wood) Manufacturing', 5, 894),
(903, 'NAICS', 33792, 'Blind and Shade Manufacturing', 4, 899),
(901, 'NAICS', 33791, 'Mattress Manufacturing', 4, 899),
(900, 'NAICS', 337910, 'Mattress Manufacturing', 5, 901),
(902, 'NAICS', 337920, 'Blind and Shade Manufacturing', 5, 903),
(912, 'NAICS', 3399, 'Other Miscellaneous Manufacturing', 3, 904),
(905, 'NAICS', 3391, 'Medical Equipment and Supplies Manufacturing', 3, 904),
(906, 'NAICS', 33911, 'Medical Equipment and Supplies Manufacturing', 4, 905),
(908, 'NAICS', 339113, 'Surgical Appliance and Supplies Manufacturing', 5, 906),
(911, 'NAICS', 339116, 'Dental Laboratories', 5, 906),
(910, 'NAICS', 339115, 'Ophthalmic Goods Manufacturing', 5, 906),
(909, 'NAICS', 339114, 'Dental Equipment and Supplies Manufacturing', 5, 906),
(907, 'NAICS', 339112, 'Surgical and Medical Instrument Manufacturing', 5, 906),
(918, 'NAICS', 33993, 'Doll, Toy, and Game Manufacturing', 4, 912),
(914, 'NAICS', 33991, 'Jewelry and Silverware Manufacturing', 4, 912),
(922, 'NAICS', 33995, 'Sign Manufacturing', 4, 912),
(923, 'NAICS', 33999, 'All Other Miscellaneous Manufacturing', 4, 912),
(920, 'NAICS', 33994, 'Office Supplies (except Paper) Manufacturing', 4, 912),
(916, 'NAICS', 33992, 'Sporting and Athletic Goods Manufacturing', 4, 912),
(913, 'NAICS', 339910, 'Jewelry and Silverware Manufacturing', 5, 914),
(915, 'NAICS', 339920, 'Sporting and Athletic Goods Manufacturing', 5, 916),
(917, 'NAICS', 339930, 'Doll, Toy, and Game Manufacturing', 5, 918),
(919, 'NAICS', 339940, 'Office Supplies (except Paper) Manufacturing', 5, 920),
(921, 'NAICS', 339950, 'Sign Manufacturing', 5, 922),
(925, 'NAICS', 339992, 'Musical Instrument Manufacturing', 5, 923),
(924, 'NAICS', 339991, 'Gasket, Packing, and Sealing Device Manufacturing', 5, 923),
(926, 'NAICS', 339993, 'Fastener, Button, Needle, and Pin Manufacturing', 5, 923),
(927, 'NAICS', 339994, 'Broom, Brush, and Mop Manufacturing', 5, 923),
(928, 'NAICS', 339995, 'Burial Casket Manufacturing', 5, 923),
(929, 'NAICS', 339999, 'All Other Miscellaneous Manufacturing', 5, 923),
(1057, 'NAICS', 424520, 'Livestock Merchant Wholesalers', 5, 1058),
(1089, 'NAICS', 425, 'Wholesale Electronic Markets and Agents and Brokers', 2, 930),
(931, 'NAICS', 423, 'Merchant Wholesalers, Durable Goods', 2, 930),
(1015, 'NAICS', 424, 'Merchant Wholesalers, Nondurable Goods', 2, 930),
(1004, 'NAICS', 4239, 'Miscellaneous Durable Goods Merchant Wholesalers', 3, 931),
(991, 'NAICS', 4238, 'Machinery, Equipment, and Supplies Merchant Wholesalers', 3, 931),
(975, 'NAICS', 4236, 'Household Appliances and Electrical and Electronic Goods Merchant Wholesalers', 3, 931),
(982, 'NAICS', 4237, 'Hardware, and Plumbing and Heating Equipment and Supplies Merchant Wholesalers', 3, 931),
(941, 'NAICS', 4232, 'Furniture and Home Furnishing Merchant Wholesalers', 3, 931),
(970, 'NAICS', 4235, 'Metal and Mineral (except Petroleum) Merchant Wholesalers', 3, 931),
(946, 'NAICS', 4233, 'Lumber and Other Construction Materials Merchant Wholesalers', 3, 931),
(932, 'NAICS', 4231, 'Motor Vehicle and Motor Vehicle Parts and Supplies Merchant Wholesalers', 3, 931),
(955, 'NAICS', 4234, 'Professional and Commercial Equipment and Supplies Merchant Wholesalers', 3, 931),
(938, 'NAICS', 42313, 'Tire and Tube Merchant Wholesalers', 4, 932),
(940, 'NAICS', 42314, 'Motor Vehicle Parts (Used) Merchant Wholesalers', 4, 932),
(934, 'NAICS', 42311, 'Automobile and Other Motor Vehicle Merchant Wholesalers', 4, 932),
(936, 'NAICS', 42312, 'Motor Vehicle Supplies and New Parts Merchant Wholesalers', 4, 932),
(933, 'NAICS', 423110, 'Automobile and Other Motor Vehicle Merchant Wholesalers', 5, 934),
(935, 'NAICS', 423120, 'Motor Vehicle Supplies and New Parts Merchant Wholesalers', 5, 936),
(937, 'NAICS', 423130, 'Tire and Tube Merchant Wholesalers', 5, 938),
(939, 'NAICS', 423140, 'Motor Vehicle Parts (Used) Merchant Wholesalers', 5, 940),
(943, 'NAICS', 42321, 'Furniture Merchant Wholesalers', 4, 941),
(945, 'NAICS', 42322, 'Home Furnishing Merchant Wholesalers', 4, 941),
(942, 'NAICS', 423210, 'Furniture Merchant Wholesalers', 5, 943),
(1144, 'NAICS', 4451, 'Grocery Stores', 3, 1143),
(944, 'NAICS', 423220, 'Home Furnishing Merchant Wholesalers', 5, 945),
(948, 'NAICS', 42331, 'Lumber, Plywood, Millwork, and Wood Panel Merchant Wholesalers', 4, 946),
(952, 'NAICS', 42333, 'Roofing, Siding, and Insulation Material Merchant Wholesalers', 4, 946),
(954, 'NAICS', 42339, 'Other Construction Material Merchant Wholesalers', 4, 946),
(950, 'NAICS', 42332, 'Brick, Stone, and Related Construction Material Merchant Wholesalers', 4, 946),
(947, 'NAICS', 423310, 'Lumber, Plywood, Millwork, and Wood Panel Merchant Wholesalers', 5, 948),
(949, 'NAICS', 423320, 'Brick, Stone, and Related Construction Material Merchant Wholesalers', 5, 950),
(951, 'NAICS', 423330, 'Roofing, Siding, and Insulation Material Merchant Wholesalers', 5, 952),
(953, 'NAICS', 423390, 'Other Construction Material Merchant Wholesalers', 5, 954),
(961, 'NAICS', 42343, 'Computer and Computer Peripheral Equipment and Software Merchant Wholesalers', 4, 955),
(965, 'NAICS', 42345, 'Medical, Dental, and Hospital Equipment and Supplies Merchant Wholesalers', 4, 955),
(959, 'NAICS', 42342, 'Office Equipment Merchant Wholesalers', 4, 955),
(969, 'NAICS', 42349, 'Other Professional Equipment and Supplies Merchant Wholesalers', 4, 955),
(963, 'NAICS', 42344, 'Other Commercial Equipment Merchant Wholesalers', 4, 955),
(967, 'NAICS', 42346, 'Ophthalmic Goods Merchant Wholesalers', 4, 955),
(957, 'NAICS', 42341, 'Photographic Equipment and Supplies Merchant Wholesalers', 4, 955),
(956, 'NAICS', 423410, 'Photographic Equipment and Supplies Merchant Wholesalers', 5, 957),
(958, 'NAICS', 423420, 'Office Equipment Merchant Wholesalers', 5, 959),
(1157, 'NAICS', 445291, 'Baked Goods Stores', 5, 1156),
(960, 'NAICS', 423430, 'Computer and Computer Peripheral Equipment and Software Merchant Wholesalers', 5, 961),
(962, 'NAICS', 423440, 'Other Commercial Equipment Merchant Wholesalers', 5, 963),
(964, 'NAICS', 423450, 'Medical, Dental, and Hospital Equipment and Supplies Merchant Wholesalers', 5, 965),
(966, 'NAICS', 423460, 'Ophthalmic Goods Merchant Wholesalers', 5, 967),
(968, 'NAICS', 423490, 'Other Professional Equipment and Supplies Merchant Wholesalers', 5, 969),
(974, 'NAICS', 42352, 'Coal and Other Mineral and Ore Merchant Wholesalers', 4, 970),
(972, 'NAICS', 42351, 'Metal Service Centers and Other Metal Merchant Wholesalers', 4, 970),
(971, 'NAICS', 423510, 'Metal Service Centers and Other Metal Merchant Wholesalers', 5, 972),
(973, 'NAICS', 423520, 'Coal and Other Mineral and Ore Merchant Wholesalers', 5, 974),
(981, 'NAICS', 42369, 'Other Electronic Parts and Equipment Merchant Wholesalers', 4, 975),
(979, 'NAICS', 42362, 'Household Appliances, Electric Housewares, and Consumer Electronics Merchant Wholesalers', 4, 975),
(977, 'NAICS', 42361, 'Electrical Apparatus and Equipment, Wiring Supplies, and Related Equipment Merchant Wholesalers', 4, 975),
(976, 'NAICS', 423610, 'Electrical Apparatus and Equipment, Wiring Supplies, and Related Equipment Merchant Wholesalers', 5, 977),
(978, 'NAICS', 423620, 'Household Appliances, Electric Housewares, and Consumer Electronics Merchant Wholesalers', 5, 979),
(980, 'NAICS', 423690, 'Other Electronic Parts and Equipment Merchant Wholesalers', 5, 981),
(986, 'NAICS', 42372, 'Plumbing and Heating Equipment and Supplies (Hydronics) Merchant Wholesalers', 4, 982),
(984, 'NAICS', 42371, 'Hardware Merchant Wholesalers', 4, 982),
(988, 'NAICS', 42373, 'Warm Air Heating and Air-Conditioning Equipment and Supplies Merchant Wholesalers', 4, 982),
(990, 'NAICS', 42374, 'Refrigeration Equipment and Supplies Merchant Wholesalers', 4, 982),
(983, 'NAICS', 423710, 'Hardware Merchant Wholesalers', 5, 984),
(985, 'NAICS', 423720, 'Plumbing and Heating Equipment and Supplies (Hydronics) Merchant Wholesalers', 5, 986),
(987, 'NAICS', 423730, 'Warm Air Heating and Air-Conditioning Equipment and Supplies Merchant Wholesalers', 5, 988),
(989, 'NAICS', 423740, 'Refrigeration Equipment and Supplies Merchant Wholesalers', 5, 990),
(999, 'NAICS', 42384, 'Industrial Supplies Merchant Wholesalers', 4, 991),
(1059, 'NAICS', 424590, 'Other Farm Product Raw Material Merchant Wholesalers', 5, 1060),
(993, 'NAICS', 42381, 'Construction and Mining (except Oil Well) Machinery and Equipment Merchant Wholesalers', 4, 991),
(995, 'NAICS', 42382, 'Farm and Garden Machinery and Equipment Merchant Wholesalers', 4, 991),
(997, 'NAICS', 42383, 'Industrial Machinery and Equipment Merchant Wholesalers', 4, 991),
(1001, 'NAICS', 42385, 'Service Establishment Equipment and Supplies Merchant Wholesalers', 4, 991),
(1003, 'NAICS', 42386, 'Transportation Equipment and Supplies (except Motor Vehicle) Merchant Wholesalers', 4, 991),
(992, 'NAICS', 423810, 'Construction and Mining (except Oil Well) Machinery and Equipment Merchant Wholesalers', 5, 993),
(994, 'NAICS', 423820, 'Farm and Garden Machinery and Equipment Merchant Wholesalers', 5, 995),
(996, 'NAICS', 423830, 'Industrial Machinery and Equipment Merchant Wholesalers', 5, 997),
(998, 'NAICS', 423840, 'Industrial Supplies Merchant Wholesalers', 5, 999),
(1000, 'NAICS', 423850, 'Service Establishment Equipment and Supplies Merchant Wholesalers', 5, 1001),
(1002, 'NAICS', 423860, 'Transportation Equipment and Supplies (except Motor Vehicle) Merchant Wholesalers', 5, 1003),
(1012, 'NAICS', 42394, 'Jewelry, Watch, Precious Stone, and Precious Metal Merchant Wholesalers', 4, 1004),
(1006, 'NAICS', 42391, 'Sporting and Recreational Goods and Supplies Merchant Wholesalers', 4, 1004),
(1008, 'NAICS', 42392, 'Toy and Hobby Goods and Supplies Merchant Wholesalers', 4, 1004),
(1010, 'NAICS', 42393, 'Recyclable Material Merchant Wholesalers', 4, 1004),
(1014, 'NAICS', 42399, 'Other Miscellaneous Durable Goods Merchant Wholesalers', 4, 1004),
(1005, 'NAICS', 423910, 'Sporting and Recreational Goods and Supplies Merchant Wholesalers', 5, 1006),
(1007, 'NAICS', 423920, 'Toy and Hobby Goods and Supplies Merchant Wholesalers', 5, 1008),
(1009, 'NAICS', 423930, 'Recyclable Material Merchant Wholesalers', 5, 1010),
(1011, 'NAICS', 423940, 'Jewelry, Watch, Precious Stone, and Precious Metal Merchant Wholesalers', 5, 1012),
(1013, 'NAICS', 423990, 'Other Miscellaneous Durable Goods Merchant Wholesalers', 5, 1014),
(1155, 'NAICS', 44523, 'Fruit and Vegetable Markets', 4, 1149),
(1066, 'NAICS', 4247, 'Petroleum and Petroleum Products Merchant Wholesalers', 3, 1015),
(1016, 'NAICS', 4241, 'Paper and Paper Product Merchant Wholesalers', 3, 1015),
(1023, 'NAICS', 4242, 'Drugs and Druggists'' Sundries Merchant Wholesalers', 3, 1015),
(1246, 'NAICS', 453991, 'Tobacco Stores', 5, 1245),
(1026, 'NAICS', 4243, 'Apparel, Piece Goods, and Notions Merchant Wholesalers', 3, 1015),
(1071, 'NAICS', 4248, 'Beer, Wine, and Distilled Alcoholic Beverage Merchant Wholesalers', 3, 1015),
(1054, 'NAICS', 4245, 'Farm Product Raw Material Merchant Wholesalers', 3, 1015),
(1061, 'NAICS', 4246, 'Chemical and Allied Products Merchant Wholesalers', 3, 1015),
(1076, 'NAICS', 4249, 'Miscellaneous Nondurable Goods Merchant Wholesalers', 3, 1015),
(1035, 'NAICS', 4244, 'Grocery and Related Product Merchant Wholesalers', 3, 1015),
(1018, 'NAICS', 42411, 'Printing and Writing Paper Merchant Wholesalers', 4, 1016),
(1020, 'NAICS', 42412, 'Stationery and Office Supplies Merchant Wholesalers', 4, 1016),
(1022, 'NAICS', 42413, 'Industrial and Personal Service Paper Merchant Wholesalers', 4, 1016),
(1017, 'NAICS', 424110, 'Printing and Writing Paper Merchant Wholesalers', 5, 1018),
(1019, 'NAICS', 424120, 'Stationery and Office Supplies Merchant Wholesalers', 5, 1020),
(1021, 'NAICS', 424130, 'Industrial and Personal Service Paper Merchant Wholesalers', 5, 1022),
(1025, 'NAICS', 42421, 'Drugs and Druggists'' Sundries Merchant Wholesalers', 4, 1023),
(1024, 'NAICS', 424210, 'Drugs and Druggists'' Sundries Merchant Wholesalers', 5, 1025),
(1034, 'NAICS', 42434, 'Footwear Merchant Wholesalers', 4, 1026),
(1028, 'NAICS', 42431, 'Piece Goods, Notions, and Other Dry Goods Merchant Wholesalers', 4, 1026),
(1030, 'NAICS', 42432, 'Men''s and Boys'' Clothing and Furnishings Merchant Wholesalers', 4, 1026),
(1032, 'NAICS', 42433, 'Women''s, Children''s, and Infants'' Clothing and Accessories Merchant Wholesalers', 4, 1026),
(1027, 'NAICS', 424310, 'Piece Goods, Notions, and Other Dry Goods Merchant Wholesalers', 5, 1028),
(1029, 'NAICS', 424320, 'Men''s and Boys'' Clothing and Furnishings Merchant Wholesalers', 5, 1030),
(1031, 'NAICS', 424330, 'Women''s, Children''s, and Infants'' Clothing and Accessories Merchant Wholesalers', 5, 1032),
(1033, 'NAICS', 424340, 'Footwear Merchant Wholesalers', 5, 1034),
(1045, 'NAICS', 42445, 'Confectionery Merchant Wholesalers', 4, 1035),
(1047, 'NAICS', 42446, 'Fish and Seafood Merchant Wholesalers', 4, 1035),
(1051, 'NAICS', 42448, 'Fresh Fruit and Vegetable Merchant Wholesalers', 4, 1035),
(1039, 'NAICS', 42442, 'Packaged Frozen Food Merchant Wholesalers', 4, 1035),
(1041, 'NAICS', 42443, 'Dairy Product (except Dried or Canned) Merchant Wholesalers', 4, 1035),
(1043, 'NAICS', 42444, 'Poultry and Poultry Product Merchant Wholesalers', 4, 1035),
(1053, 'NAICS', 42449, 'Other Grocery and Related Products Merchant Wholesalers', 4, 1035),
(1049, 'NAICS', 42447, 'Meat and Meat Product Merchant Wholesalers', 4, 1035),
(1037, 'NAICS', 42441, 'General Line Grocery Merchant Wholesalers', 4, 1035),
(1036, 'NAICS', 424410, 'General Line Grocery Merchant Wholesalers', 5, 1037),
(1038, 'NAICS', 424420, 'Packaged Frozen Food Merchant Wholesalers', 5, 1039),
(1040, 'NAICS', 424430, 'Dairy Product (except Dried or Canned) Merchant Wholesalers', 5, 1041),
(1042, 'NAICS', 424440, 'Poultry and Poultry Product Merchant Wholesalers', 5, 1043),
(1044, 'NAICS', 424450, 'Confectionery Merchant Wholesalers', 5, 1045),
(1046, 'NAICS', 424460, 'Fish and Seafood Merchant Wholesalers', 5, 1047),
(1048, 'NAICS', 424470, 'Meat and Meat Product Merchant Wholesalers', 5, 1049),
(1050, 'NAICS', 424480, 'Fresh Fruit and Vegetable Merchant Wholesalers', 5, 1051),
(1052, 'NAICS', 424490, 'Other Grocery and Related Products Merchant Wholesalers', 5, 1053),
(1058, 'NAICS', 42452, 'Livestock Merchant Wholesalers', 4, 1054),
(1060, 'NAICS', 42459, 'Other Farm Product Raw Material Merchant Wholesalers', 4, 1054),
(1056, 'NAICS', 42451, 'Grain and Field Bean Merchant Wholesalers', 4, 1054),
(1055, 'NAICS', 424510, 'Grain and Field Bean Merchant Wholesalers', 5, 1056),
(1065, 'NAICS', 42469, 'Other Chemical and Allied Products Merchant Wholesalers', 4, 1061),
(1063, 'NAICS', 42461, 'Plastics Materials and Basic Forms and Shapes Merchant Wholesalers', 4, 1061),
(1062, 'NAICS', 424610, 'Plastics Materials and Basic Forms and Shapes Merchant Wholesalers', 5, 1063),
(1064, 'NAICS', 424690, 'Other Chemical and Allied Products Merchant Wholesalers', 5, 1065),
(1070, 'NAICS', 42472, 'Petroleum and Petroleum Products Merchant Wholesalers (except Bulk Stations and Terminals)', 4, 1066),
(1068, 'NAICS', 42471, 'Petroleum Bulk Stations and Terminals', 4, 1066),
(1067, 'NAICS', 424710, 'Petroleum Bulk Stations and Terminals', 5, 1068),
(1069, 'NAICS', 424720, 'Petroleum and Petroleum Products Merchant Wholesalers (except Bulk Stations and Terminals)', 5, 1070),
(1073, 'NAICS', 42481, 'Beer and Ale Merchant Wholesalers', 4, 1071),
(1075, 'NAICS', 42482, 'Wine and Distilled Alcoholic Beverage Merchant Wholesalers', 4, 1071),
(1072, 'NAICS', 424810, 'Beer and Ale Merchant Wholesalers', 5, 1073),
(1074, 'NAICS', 424820, 'Wine and Distilled Alcoholic Beverage Merchant Wholesalers', 5, 1075),
(1078, 'NAICS', 42491, 'Farm Supplies Merchant Wholesalers', 4, 1076),
(1080, 'NAICS', 42492, 'Book, Periodical, and Newspaper Merchant Wholesalers', 4, 1076),
(1082, 'NAICS', 42493, 'Flower, Nursery Stock, and Florists'' Supplies Merchant Wholesalers', 4, 1076),
(1084, 'NAICS', 42494, 'Tobacco and Tobacco Product Merchant Wholesalers', 4, 1076),
(1086, 'NAICS', 42495, 'Paint, Varnish, and Supplies Merchant Wholesalers', 4, 1076),
(1088, 'NAICS', 42499, 'Other Miscellaneous Nondurable Goods Merchant Wholesalers', 4, 1076),
(1077, 'NAICS', 424910, 'Farm Supplies Merchant Wholesalers', 5, 1078),
(1079, 'NAICS', 424920, 'Book, Periodical, and Newspaper Merchant Wholesalers', 5, 1080),
(1081, 'NAICS', 424930, 'Flower, Nursery Stock, and Florists'' Supplies Merchant Wholesalers', 5, 1082),
(1083, 'NAICS', 424940, 'Tobacco and Tobacco Product Merchant Wholesalers', 5, 1084),
(1085, 'NAICS', 424950, 'Paint, Varnish, and Supplies Merchant Wholesalers', 5, 1086),
(1087, 'NAICS', 424990, 'Other Miscellaneous Nondurable Goods Merchant Wholesalers', 5, 1088),
(1090, 'NAICS', 4251, 'Wholesale Electronic Markets and Agents and Brokers', 3, 1089),
(1092, 'NAICS', 42511, 'Business to Business Electronic Markets', 4, 1090),
(1094, 'NAICS', 42512, 'Wholesale Trade Agents and Brokers', 4, 1090),
(1091, 'NAICS', 425110, 'Business to Business Electronic Markets', 5, 1092),
(1093, 'NAICS', 425120, 'Wholesale Trade Agents and Brokers', 5, 1094),
(1163, 'NAICS', 446, 'Health and Personal Care Stores', 2, 1095),
(1180, 'NAICS', 448, 'Clothing and Clothing Accessories Stores', 2, 1095),
(1174, 'NAICS', 447, 'Gasoline Stations', 2, 1095),
(1096, 'NAICS', 441, 'Motor Vehicle and Parts Dealers', 2, 1095),
(1113, 'NAICS', 442, 'Furniture and Home Furnishings Stores', 2, 1095),
(1123, 'NAICS', 443, 'Electronics and Appliance Stores', 2, 1095),
(1128, 'NAICS', 444, 'Building Material and Garden Equipment and Supplies Dealers', 2, 1095),
(1143, 'NAICS', 445, 'Food and Beverage Stores', 2, 1095),
(1226, 'NAICS', 453, 'Miscellaneous Store Retailers', 2, 1095),
(1248, 'NAICS', 454, 'Nonstore Retailers', 2, 1095),
(1216, 'NAICS', 452, 'General Merchandise Stores', 2, 1095),
(1202, 'NAICS', 451, 'Sporting Goods, Hobby, Musical Instrument, and Book Stores', 2, 1095),
(1102, 'NAICS', 4412, 'Other Motor Vehicle Dealers', 3, 1096),
(1097, 'NAICS', 4411, 'Automobile Dealers', 3, 1096),
(1108, 'NAICS', 4413, 'Automotive Parts, Accessories, and Tire Stores', 3, 1096),
(1099, 'NAICS', 44111, 'New Car Dealers', 4, 1097),
(1101, 'NAICS', 44112, 'Used Car Dealers', 4, 1097),
(1098, 'NAICS', 441110, 'New Car Dealers', 5, 1099),
(1100, 'NAICS', 441120, 'Used Car Dealers', 5, 1101),
(1104, 'NAICS', 44121, 'Recreational Vehicle Dealers', 4, 1102),
(1105, 'NAICS', 44122, 'Motorcycle, Boat, and Other Motor Vehicle Dealers', 4, 1102),
(1103, 'NAICS', 441210, 'Recreational Vehicle Dealers', 5, 1104),
(1106, 'NAICS', 441222, 'Boat Dealers', 5, 1105),
(1107, 'NAICS', 441228, 'Motorcycle, ATV, and All Other Motor Vehicle Dealers', 5, 1105),
(1112, 'NAICS', 44132, 'Tire Dealers', 4, 1108),
(1110, 'NAICS', 44131, 'Automotive Parts and Accessories Stores', 4, 1108),
(1109, 'NAICS', 441310, 'Automotive Parts and Accessories Stores', 5, 1110),
(1111, 'NAICS', 441320, 'Tire Dealers', 5, 1112),
(1114, 'NAICS', 4421, 'Furniture Stores', 3, 1113),
(1117, 'NAICS', 4422, 'Home Furnishings Stores', 3, 1113),
(1116, 'NAICS', 44211, 'Furniture Stores', 4, 1114),
(1115, 'NAICS', 442110, 'Furniture Stores', 5, 1116),
(1120, 'NAICS', 44229, 'Other Home Furnishings Stores', 4, 1117),
(1119, 'NAICS', 44221, 'Floor Covering Stores', 4, 1117),
(1118, 'NAICS', 442210, 'Floor Covering Stores', 5, 1119),
(1122, 'NAICS', 442299, 'All Other Home Furnishings Stores', 5, 1120),
(1121, 'NAICS', 442291, 'Window Treatment Stores', 5, 1120),
(1124, 'NAICS', 4431, 'Electronics and Appliance Stores', 3, 1123),
(1125, 'NAICS', 44314, 'Electronics and Appliance Stores', 4, 1124),
(1126, 'NAICS', 443141, 'Household Appliance Stores', 5, 1125),
(1127, 'NAICS', 443142, 'Electronics Stores', 5, 1125),
(1129, 'NAICS', 4441, 'Building Material and Supplies Dealers', 3, 1128),
(1138, 'NAICS', 4442, 'Lawn and Garden Equipment and Supplies Stores', 3, 1128),
(1137, 'NAICS', 44419, 'Other Building Material Dealers', 4, 1129),
(1131, 'NAICS', 44411, 'Home Centers', 4, 1129),
(1133, 'NAICS', 44412, 'Paint and Wallpaper Stores', 4, 1129),
(1135, 'NAICS', 44413, 'Hardware Stores', 4, 1129),
(1130, 'NAICS', 444110, 'Home Centers', 5, 1131),
(1132, 'NAICS', 444120, 'Paint and Wallpaper Stores', 5, 1133),
(1134, 'NAICS', 444130, 'Hardware Stores', 5, 1135),
(1136, 'NAICS', 444190, 'Other Building Material Dealers', 5, 1137),
(1140, 'NAICS', 44421, 'Outdoor Power Equipment Stores', 4, 1138),
(1142, 'NAICS', 44422, 'Nursery, Garden Center, and Farm Supply Stores', 4, 1138),
(1139, 'NAICS', 444210, 'Outdoor Power Equipment Stores', 5, 1140),
(1141, 'NAICS', 444220, 'Nursery, Garden Center, and Farm Supply Stores', 5, 1142),
(1149, 'NAICS', 4452, 'Specialty Food Stores', 3, 1143),
(1160, 'NAICS', 4453, 'Beer, Wine, and Liquor Stores', 3, 1143),
(1148, 'NAICS', 44512, 'Convenience Stores', 4, 1144),
(1146, 'NAICS', 44511, 'Supermarkets and Other Grocery (except Convenience) Stores', 4, 1144),
(1145, 'NAICS', 445110, 'Supermarkets and Other Grocery (except Convenience) Stores', 5, 1146),
(1147, 'NAICS', 445120, 'Convenience Stores', 5, 1148),
(1153, 'NAICS', 44522, 'Fish and Seafood Markets', 4, 1149),
(1156, 'NAICS', 44529, 'Other Specialty Food Stores', 4, 1149),
(1150, 'NAICS', 445210, 'Meat Markets', 5, 1151),
(1152, 'NAICS', 445220, 'Fish and Seafood Markets', 5, 1153),
(1154, 'NAICS', 445230, 'Fruit and Vegetable Markets', 5, 1155),
(1158, 'NAICS', 445292, 'Confectionery and Nut Stores', 5, 1156),
(1159, 'NAICS', 445299, 'All Other Specialty Food Stores', 5, 1156),
(1162, 'NAICS', 44531, 'Beer, Wine, and Liquor Stores', 4, 1160),
(1161, 'NAICS', 445310, 'Beer, Wine, and Liquor Stores', 5, 1162),
(1164, 'NAICS', 4461, 'Health and Personal Care Stores', 3, 1163),
(1171, 'NAICS', 44619, 'Other Health and Personal Care Stores', 4, 1164),
(1166, 'NAICS', 44611, 'Pharmacies and Drug Stores', 4, 1164),
(1168, 'NAICS', 44612, 'Cosmetics, Beauty Supplies, and Perfume Stores', 4, 1164),
(1170, 'NAICS', 44613, 'Optical Goods Stores', 4, 1164),
(1165, 'NAICS', 446110, 'Pharmacies and Drug Stores', 5, 1166),
(1167, 'NAICS', 446120, 'Cosmetics, Beauty Supplies, and Perfume Stores', 5, 1168),
(1169, 'NAICS', 446130, 'Optical Goods Stores', 5, 1170),
(1173, 'NAICS', 446199, 'All Other Health and Personal Care Stores', 5, 1171),
(1172, 'NAICS', 446191, 'Food (Health) Supplement Stores', 5, 1171),
(1175, 'NAICS', 4471, 'Gasoline Stations', 3, 1174),
(1179, 'NAICS', 44719, 'Other Gasoline Stations', 4, 1175),
(1177, 'NAICS', 44711, 'Gasoline Stations with Convenience Stores', 4, 1175),
(1176, 'NAICS', 447110, 'Gasoline Stations with Convenience Stores', 5, 1177),
(1178, 'NAICS', 447190, 'Other Gasoline Stations', 5, 1179),
(1181, 'NAICS', 4481, 'Clothing Stores', 3, 1180),
(1197, 'NAICS', 4483, 'Jewelry, Luggage, and Leather Goods Stores', 3, 1180),
(1189, 'NAICS', 44814, 'Family Clothing Stores', 4, 1181),
(1187, 'NAICS', 44813, 'Children''s and Infants'' Clothing Stores', 4, 1181),
(1185, 'NAICS', 44812, 'Women''s Clothing Stores', 4, 1181),
(1183, 'NAICS', 44811, 'Men''s Clothing Stores', 4, 1181),
(1193, 'NAICS', 44819, 'Other Clothing Stores', 4, 1181),
(1191, 'NAICS', 44815, 'Clothing Accessories Stores', 4, 1181),
(1182, 'NAICS', 448110, 'Men''s Clothing Stores', 5, 1183),
(1184, 'NAICS', 448120, 'Women''s Clothing Stores', 5, 1185),
(1186, 'NAICS', 448130, 'Children''s and Infants'' Clothing Stores', 5, 1187),
(1188, 'NAICS', 448140, 'Family Clothing Stores', 5, 1189),
(1190, 'NAICS', 448150, 'Clothing Accessories Stores', 5, 1191),
(1192, 'NAICS', 448190, 'Other Clothing Stores', 5, 1193),
(1196, 'NAICS', 44821, 'Shoe Stores', 4, 1194),
(1195, 'NAICS', 448210, 'Shoe Stores', 5, 1196),
(1199, 'NAICS', 44831, 'Jewelry Stores', 4, 1197),
(1201, 'NAICS', 44832, 'Luggage and Leather Goods Stores', 4, 1197),
(1198, 'NAICS', 448310, 'Jewelry Stores', 5, 1199),
(1200, 'NAICS', 448320, 'Luggage and Leather Goods Stores', 5, 1201),
(1203, 'NAICS', 4511, 'Sporting Goods, Hobby, and Musical Instrument Stores', 3, 1202),
(1212, 'NAICS', 4512, 'Book Stores and News Dealers', 3, 1202),
(1205, 'NAICS', 45111, 'Sporting Goods Stores', 4, 1203),
(1207, 'NAICS', 45112, 'Hobby, Toy, and Game Stores', 4, 1203),
(1209, 'NAICS', 45113, 'Sewing, Needlework, and Piece Goods Stores', 4, 1203),
(1211, 'NAICS', 45114, 'Musical Instrument and Supplies Stores', 4, 1203),
(1204, 'NAICS', 451110, 'Sporting Goods Stores', 5, 1205),
(1206, 'NAICS', 451120, 'Hobby, Toy, and Game Stores', 5, 1207),
(1208, 'NAICS', 451130, 'Sewing, Needlework, and Piece Goods Stores', 5, 1209),
(1210, 'NAICS', 451140, 'Musical Instrument and Supplies Stores', 5, 1211),
(1213, 'NAICS', 45121, 'Book Stores and News Dealers', 4, 1212),
(1214, 'NAICS', 451211, 'Book Stores', 5, 1213),
(1215, 'NAICS', 451212, 'News Dealers and Newsstands', 5, 1213),
(1217, 'NAICS', 4521, 'Department Stores', 3, 1216),
(1221, 'NAICS', 4529, 'Other General Merchandise Stores', 3, 1216),
(1218, 'NAICS', 45211, 'Department Stores', 4, 1217),
(1220, 'NAICS', 452112, 'Discount Department Stores', 5, 1218),
(1219, 'NAICS', 452111, 'Department Stores (except Discount Department Stores)', 5, 1218),
(1223, 'NAICS', 45291, 'Warehouse Clubs and Supercenters', 4, 1221),
(1225, 'NAICS', 45299, 'All Other General Merchandise Stores', 4, 1221),
(1222, 'NAICS', 452910, 'Warehouse Clubs and Supercenters', 5, 1223),
(1224, 'NAICS', 452990, 'All Other General Merchandise Stores', 5, 1225),
(1230, 'NAICS', 4532, 'Office Supplies, Stationery, and Gift Stores', 3, 1226),
(1235, 'NAICS', 4533, 'Used Merchandise Stores', 3, 1226),
(1227, 'NAICS', 4531, 'Florists', 3, 1226),
(1238, 'NAICS', 4539, 'Other Miscellaneous Store Retailers', 3, 1226),
(1229, 'NAICS', 45311, 'Florists', 4, 1227),
(1228, 'NAICS', 453110, 'Florists', 5, 1229),
(1232, 'NAICS', 45321, 'Office Supplies and Stationery Stores', 4, 1230),
(1234, 'NAICS', 45322, 'Gift, Novelty, and Souvenir Stores', 4, 1230),
(1231, 'NAICS', 453210, 'Office Supplies and Stationery Stores', 5, 1232),
(1233, 'NAICS', 453220, 'Gift, Novelty, and Souvenir Stores', 5, 1234),
(1237, 'NAICS', 45331, 'Used Merchandise Stores', 4, 1235),
(1236, 'NAICS', 453310, 'Used Merchandise Stores', 5, 1237),
(1244, 'NAICS', 45393, 'Manufactured (Mobile) Home Dealers', 4, 1238),
(1240, 'NAICS', 45391, 'Pet and Pet Supplies Stores', 4, 1238),
(1242, 'NAICS', 45392, 'Art Dealers', 4, 1238),
(1245, 'NAICS', 45399, 'All Other Miscellaneous Store Retailers', 4, 1238),
(1239, 'NAICS', 453910, 'Pet and Pet Supplies Stores', 5, 1240),
(1241, 'NAICS', 453920, 'Art Dealers', 5, 1242),
(1243, 'NAICS', 453930, 'Manufactured (Mobile) Home Dealers', 5, 1244),
(1247, 'NAICS', 453998, 'All Other Miscellaneous Store Retailers (except Tobacco Stores)', 5, 1245),
(1254, 'NAICS', 4542, 'Vending Machine Operators', 3, 1248),
(1257, 'NAICS', 4543, 'Direct Selling Establishments', 3, 1248),
(1249, 'NAICS', 4541, 'Electronic Shopping and Mail-Order Houses', 3, 1248),
(1250, 'NAICS', 45411, 'Electronic Shopping and Mail-Order Houses', 4, 1249),
(1251, 'NAICS', 454111, 'Electronic Shopping', 5, 1250),
(1252, 'NAICS', 454112, 'Electronic Auctions', 5, 1250),
(1253, 'NAICS', 454113, 'Mail-Order Houses', 5, 1250),
(1256, 'NAICS', 45421, 'Vending Machine Operators', 4, 1254),
(1255, 'NAICS', 454210, 'Vending Machine Operators', 5, 1256),
(1259, 'NAICS', 45431, 'Fuel Dealers', 4, 1257),
(1261, 'NAICS', 45439, 'Other Direct Selling Establishments', 4, 1257),
(1258, 'NAICS', 454310, 'Fuel Dealers', 5, 1259),
(1260, 'NAICS', 454390, 'Other Direct Selling Establishments', 5, 1261),
(1303, 'NAICS', 485, 'Transit and Ground Passenger Transportation', 2, 1262),
(1381, 'NAICS', 491, 'Postal Service', 2, 1262),
(1263, 'NAICS', 481, 'Air Transportation', 2, 1262),
(1328, 'NAICS', 486, 'Pipeline Transportation', 2, 1262),
(1340, 'NAICS', 487, 'Scenic and Sightseeing Transportation', 2, 1262),
(1350, 'NAICS', 488, 'Support Activities for Transportation', 2, 1262),
(1392, 'NAICS', 493, 'Warehousing and Storage', 2, 1262),
(1278, 'NAICS', 483, 'Water Transportation', 2, 1262),
(1385, 'NAICS', 492, 'Couriers and Messengers', 2, 1262),
(1289, 'NAICS', 484, 'Truck Transportation', 2, 1262),
(1268, 'NAICS', 4812, 'Nonscheduled Air Transportation', 3, 1263),
(1264, 'NAICS', 4811, 'Scheduled Air Transportation', 3, 1263),
(1265, 'NAICS', 48111, 'Scheduled Air Transportation', 4, 1264),
(1266, 'NAICS', 481111, 'Scheduled Passenger Air Transportation', 5, 1265),
(1267, 'NAICS', 481112, 'Scheduled Freight Air Transportation', 5, 1265),
(1269, 'NAICS', 48121, 'Nonscheduled Air Transportation', 4, 1268),
(1270, 'NAICS', 481211, 'Nonscheduled Chartered Passenger Air Transportation', 5, 1269),
(1271, 'NAICS', 481212, 'Nonscheduled Chartered Freight Air Transportation', 5, 1269),
(1272, 'NAICS', 481219, 'Other Nonscheduled Air Transportation', 5, 1269),
(1274, 'NAICS', 4821, 'Rail Transportation', 3, 1273),
(1275, 'NAICS', 48211, 'Rail Transportation', 4, 1274),
(1276, 'NAICS', 482111, 'Line-Haul Railroads', 5, 1275),
(1277, 'NAICS', 482112, 'Short Line Railroads', 5, 1275),
(1279, 'NAICS', 4831, 'Deep Sea, Coastal, and Great Lakes Water Transportation', 3, 1278),
(1285, 'NAICS', 4832, 'Inland Water Transportation', 3, 1278),
(1280, 'NAICS', 48311, 'Deep Sea, Coastal, and Great Lakes Water Transportation', 4, 1279),
(1283, 'NAICS', 483113, 'Coastal and Great Lakes Freight Transportation', 5, 1280),
(1282, 'NAICS', 483112, 'Deep Sea Passenger Transportation', 5, 1280),
(1284, 'NAICS', 483114, 'Coastal and Great Lakes Passenger Transportation', 5, 1280),
(1281, 'NAICS', 483111, 'Deep Sea Freight Transportation', 5, 1280),
(1286, 'NAICS', 48321, 'Inland Water Transportation', 4, 1285),
(1288, 'NAICS', 483212, 'Inland Water Passenger Transportation', 5, 1286),
(1287, 'NAICS', 483211, 'Inland Water Freight Transportation', 5, 1286),
(1296, 'NAICS', 4842, 'Specialized Freight Trucking', 3, 1289),
(1290, 'NAICS', 4841, 'General Freight Trucking', 3, 1289),
(1293, 'NAICS', 48412, 'General Freight Trucking, Long-Distance', 4, 1290),
(1292, 'NAICS', 48411, 'General Freight Trucking, Local', 4, 1290),
(1291, 'NAICS', 484110, 'General Freight Trucking, Local', 5, 1292),
(1295, 'NAICS', 484122, 'General Freight Trucking, Long-Distance, Less Than Truckload', 5, 1293),
(1294, 'NAICS', 484121, 'General Freight Trucking, Long-Distance, Truckload', 5, 1293),
(1298, 'NAICS', 48421, 'Used Household and Office Goods Moving', 4, 1296),
(1300, 'NAICS', 48422, 'Specialized Freight (except Used Goods) Trucking, Local', 4, 1296),
(1302, 'NAICS', 48423, 'Specialized Freight (except Used Goods) Trucking, Long-Distance', 4, 1296),
(1297, 'NAICS', 484210, 'Used Household and Office Goods Moving', 5, 1298),
(1299, 'NAICS', 484220, 'Specialized Freight (except Used Goods) Trucking, Local', 5, 1300),
(1301, 'NAICS', 484230, 'Specialized Freight (except Used Goods) Trucking, Long-Distance', 5, 1302),
(1310, 'NAICS', 4852, 'Interurban and Rural Bus Transportation', 3, 1303),
(1304, 'NAICS', 4851, 'Urban Transit Systems', 3, 1303),
(1517, 'NAICS', 523120, 'Securities Brokerage', 5, 1518),
(1324, 'NAICS', 4859, 'Other Transit and Ground Passenger Transportation', 3, 1303),
(1313, 'NAICS', 4853, 'Taxi and Limousine Service', 3, 1303),
(1318, 'NAICS', 4854, 'School and Employee Bus Transportation', 3, 1303),
(1305, 'NAICS', 48511, 'Urban Transit Systems', 4, 1304),
(1308, 'NAICS', 485113, 'Bus and Other Motor Vehicle Transit Systems', 5, 1305),
(1309, 'NAICS', 485119, 'Other Urban Transit Systems', 5, 1305),
(1306, 'NAICS', 485111, 'Mixed Mode Transit Systems', 5, 1305),
(1307, 'NAICS', 485112, 'Commuter Rail Systems', 5, 1305),
(1312, 'NAICS', 48521, 'Interurban and Rural Bus Transportation', 4, 1310),
(1311, 'NAICS', 485210, 'Interurban and Rural Bus Transportation', 5, 1312),
(1315, 'NAICS', 48531, 'Taxi Service', 4, 1313),
(1317, 'NAICS', 48532, 'Limousine Service', 4, 1313),
(1314, 'NAICS', 485310, 'Taxi Service', 5, 1315),
(1316, 'NAICS', 485320, 'Limousine Service', 5, 1317),
(1320, 'NAICS', 48541, 'School and Employee Bus Transportation', 4, 1318),
(1319, 'NAICS', 485410, 'School and Employee Bus Transportation', 5, 1320),
(1323, 'NAICS', 48551, 'Charter Bus Industry', 4, 1321),
(1322, 'NAICS', 485510, 'Charter Bus Industry', 5, 1323),
(1325, 'NAICS', 48599, 'Other Transit and Ground Passenger Transportation', 4, 1324),
(1327, 'NAICS', 485999, 'All Other Transit and Ground Passenger Transportation', 5, 1325),
(1326, 'NAICS', 485991, 'Special Needs Transportation', 5, 1325),
(1329, 'NAICS', 4861, 'Pipeline Transportation of Crude Oil', 3, 1328),
(1335, 'NAICS', 4869, 'Other Pipeline Transportation', 3, 1328),
(1332, 'NAICS', 4862, 'Pipeline Transportation of Natural Gas', 3, 1328),
(1331, 'NAICS', 48611, 'Pipeline Transportation of Crude Oil', 4, 1329),
(1330, 'NAICS', 486110, 'Pipeline Transportation of Crude Oil', 5, 1331),
(1334, 'NAICS', 48621, 'Pipeline Transportation of Natural Gas', 4, 1332),
(1333, 'NAICS', 486210, 'Pipeline Transportation of Natural Gas', 5, 1334),
(1337, 'NAICS', 48691, 'Pipeline Transportation of Refined Petroleum Products', 4, 1335),
(1339, 'NAICS', 48699, 'All Other Pipeline Transportation', 4, 1335),
(1336, 'NAICS', 486910, 'Pipeline Transportation of Refined Petroleum Products', 5, 1337),
(1338, 'NAICS', 486990, 'All Other Pipeline Transportation', 5, 1339),
(1344, 'NAICS', 4872, 'Scenic and Sightseeing Transportation, Water', 3, 1340),
(1347, 'NAICS', 4879, 'Scenic and Sightseeing Transportation, Other', 3, 1340),
(1341, 'NAICS', 4871, 'Scenic and Sightseeing Transportation, Land', 3, 1340),
(1343, 'NAICS', 48711, 'Scenic and Sightseeing Transportation, Land', 4, 1341),
(1342, 'NAICS', 487110, 'Scenic and Sightseeing Transportation, Land', 5, 1343),
(1346, 'NAICS', 48721, 'Scenic and Sightseeing Transportation, Water', 4, 1344),
(1345, 'NAICS', 487210, 'Scenic and Sightseeing Transportation, Water', 5, 1346),
(1349, 'NAICS', 48799, 'Scenic and Sightseeing Transportation, Other', 4, 1347),
(1348, 'NAICS', 487990, 'Scenic and Sightseeing Transportation, Other', 5, 1349),
(1377, 'NAICS', 4889, 'Other Support Activities for Transportation', 3, 1350),
(1351, 'NAICS', 4881, 'Support Activities for Air Transportation', 3, 1350),
(1357, 'NAICS', 4882, 'Support Activities for Rail Transportation', 3, 1350),
(1360, 'NAICS', 4883, 'Support Activities for Water Transportation', 3, 1350),
(1369, 'NAICS', 4884, 'Support Activities for Road Transportation', 3, 1350),
(1374, 'NAICS', 4885, 'Freight Transportation Arrangement', 3, 1350),
(1352, 'NAICS', 48811, 'Airport Operations', 4, 1351),
(1356, 'NAICS', 48819, 'Other Support Activities for Air Transportation', 4, 1351),
(1353, 'NAICS', 488111, 'Air Traffic Control', 5, 1352),
(1354, 'NAICS', 488119, 'Other Airport Operations', 5, 1352),
(1355, 'NAICS', 488190, 'Other Support Activities for Air Transportation', 5, 1356),
(1359, 'NAICS', 48821, 'Support Activities for Rail Transportation', 4, 1357),
(1358, 'NAICS', 488210, 'Support Activities for Rail Transportation', 5, 1359),
(1362, 'NAICS', 48831, 'Port and Harbor Operations', 4, 1360),
(1366, 'NAICS', 48833, 'Navigational Services to Shipping', 4, 1360),
(1368, 'NAICS', 48839, 'Other Support Activities for Water Transportation', 4, 1360),
(1364, 'NAICS', 48832, 'Marine Cargo Handling', 4, 1360),
(1361, 'NAICS', 488310, 'Port and Harbor Operations', 5, 1362),
(1363, 'NAICS', 488320, 'Marine Cargo Handling', 5, 1364),
(1365, 'NAICS', 488330, 'Navigational Services to Shipping', 5, 1366),
(1367, 'NAICS', 488390, 'Other Support Activities for Water Transportation', 5, 1368),
(1373, 'NAICS', 48849, 'Other Support Activities for Road Transportation', 4, 1369),
(1371, 'NAICS', 48841, 'Motor Vehicle Towing', 4, 1369),
(1370, 'NAICS', 488410, 'Motor Vehicle Towing', 5, 1371),
(1372, 'NAICS', 488490, 'Other Support Activities for Road Transportation', 5, 1373),
(1376, 'NAICS', 48851, 'Freight Transportation Arrangement', 4, 1374),
(1375, 'NAICS', 488510, 'Freight Transportation Arrangement', 5, 1376),
(1378, 'NAICS', 48899, 'Other Support Activities for Transportation', 4, 1377),
(1379, 'NAICS', 488991, 'Packing and Crating', 5, 1378),
(1380, 'NAICS', 488999, 'All Other Support Activities for Transportation', 5, 1378),
(1382, 'NAICS', 4911, 'Postal Service', 3, 1381),
(1384, 'NAICS', 49111, 'Postal Service', 4, 1382),
(1383, 'NAICS', 491110, 'Postal Service', 5, 1384),
(1386, 'NAICS', 4921, 'Couriers and Express Delivery Services', 3, 1385),
(1389, 'NAICS', 4922, 'Local Messengers and Local Delivery', 3, 1385),
(1388, 'NAICS', 49211, 'Couriers and Express Delivery Services', 4, 1386),
(1387, 'NAICS', 492110, 'Couriers and Express Delivery Services', 5, 1388),
(1391, 'NAICS', 49221, 'Local Messengers and Local Delivery', 4, 1389),
(1390, 'NAICS', 492210, 'Local Messengers and Local Delivery', 5, 1391),
(1393, 'NAICS', 4931, 'Warehousing and Storage', 3, 1392),
(1401, 'NAICS', 49319, 'Other Warehousing and Storage', 4, 1393),
(1395, 'NAICS', 49311, 'General Warehousing and Storage', 4, 1393),
(1397, 'NAICS', 49312, 'Refrigerated Warehousing and Storage', 4, 1393),
(1399, 'NAICS', 49313, 'Farm Product Warehousing and Storage', 4, 1393),
(1394, 'NAICS', 493110, 'General Warehousing and Storage', 5, 1395),
(1396, 'NAICS', 493120, 'Refrigerated Warehousing and Storage', 5, 1397),
(1398, 'NAICS', 493130, 'Farm Product Warehousing and Storage', 5, 1399),
(1400, 'NAICS', 493190, 'Other Warehousing and Storage', 5, 1401),
(1403, 'NAICS', 511, 'Publishing Industries (except Internet)', 2, 1402),
(1442, 'NAICS', 515, 'Broadcasting (except Internet)', 2, 1402),
(1470, 'NAICS', 519, 'Other Information Services', 2, 1402),
(1419, 'NAICS', 512, 'Motion Picture and Sound Recording Industries', 2, 1402),
(1452, 'NAICS', 517, 'Telecommunications', 2, 1402),
(1466, 'NAICS', 518, 'Data Processing, Hosting, and Related Services', 2, 1402),
(1416, 'NAICS', 5112, 'Software Publishers', 3, 1403),
(1404, 'NAICS', 5111, 'Newspaper, Periodical, Book, and Directory Publishers', 3, 1403),
(1412, 'NAICS', 51114, 'Directory and Mailing List Publishers', 4, 1404),
(1413, 'NAICS', 51119, 'Other Publishers', 4, 1404),
(1408, 'NAICS', 51112, 'Periodical Publishers', 4, 1404),
(1410, 'NAICS', 51113, 'Book Publishers', 4, 1404),
(1406, 'NAICS', 51111, 'Newspaper Publishers', 4, 1404),
(1405, 'NAICS', 511110, 'Newspaper Publishers', 5, 1406),
(1407, 'NAICS', 511120, 'Periodical Publishers', 5, 1408),
(1409, 'NAICS', 511130, 'Book Publishers', 5, 1410),
(1411, 'NAICS', 511140, 'Directory and Mailing List Publishers', 5, 1412),
(1414, 'NAICS', 511191, 'Greeting Card Publishers', 5, 1413),
(1415, 'NAICS', 511199, 'All Other Publishers', 5, 1413),
(1418, 'NAICS', 51121, 'Software Publishers', 4, 1416),
(1417, 'NAICS', 511210, 'Software Publishers', 5, 1418),
(1420, 'NAICS', 5121, 'Motion Picture and Video Industries', 3, 1419),
(1431, 'NAICS', 5122, 'Sound Recording Industries', 3, 1419),
(1428, 'NAICS', 51219, 'Postproduction Services and Other Motion Picture and Video Industries', 4, 1420),
(1422, 'NAICS', 51211, 'Motion Picture and Video Production', 4, 1420),
(1424, 'NAICS', 51212, 'Motion Picture and Video Distribution', 4, 1420),
(1425, 'NAICS', 51213, 'Motion Picture and Video Exhibition', 4, 1420),
(1421, 'NAICS', 512110, 'Motion Picture and Video Production', 5, 1422),
(1423, 'NAICS', 512120, 'Motion Picture and Video Distribution', 5, 1424),
(1426, 'NAICS', 512131, 'Motion Picture Theaters (except Drive-Ins)', 5, 1425),
(1427, 'NAICS', 512132, 'Drive-In Motion Picture Theaters', 5, 1425),
(1430, 'NAICS', 512199, 'Other Motion Picture and Video Industries', 5, 1428),
(1429, 'NAICS', 512191, 'Teleproduction and Other Postproduction Services', 5, 1428),
(1441, 'NAICS', 51229, 'Other Sound Recording Industries', 4, 1431),
(1435, 'NAICS', 51222, 'Integrated Record Production/Distribution', 4, 1431),
(1437, 'NAICS', 51223, 'Music Publishers', 4, 1431),
(1433, 'NAICS', 51221, 'Record Production', 4, 1431),
(1439, 'NAICS', 51224, 'Sound Recording Studios', 4, 1431),
(1432, 'NAICS', 512210, 'Record Production', 5, 1433),
(1434, 'NAICS', 512220, 'Integrated Record Production/Distribution', 5, 1435),
(1436, 'NAICS', 512230, 'Music Publishers', 5, 1437),
(1438, 'NAICS', 512240, 'Sound Recording Studios', 5, 1439),
(1440, 'NAICS', 512290, 'Other Sound Recording Industries', 5, 1441),
(1449, 'NAICS', 5152, 'Cable and Other Subscription Programming', 3, 1442),
(1443, 'NAICS', 5151, 'Radio and Television Broadcasting', 3, 1442),
(1444, 'NAICS', 51511, 'Radio Broadcasting', 4, 1443),
(1448, 'NAICS', 51512, 'Television Broadcasting', 4, 1443),
(1445, 'NAICS', 515111, 'Radio Networks', 5, 1444),
(1446, 'NAICS', 515112, 'Radio Stations', 5, 1444),
(1447, 'NAICS', 515120, 'Television Broadcasting', 5, 1448),
(1451, 'NAICS', 51521, 'Cable and Other Subscription Programming', 4, 1449),
(1450, 'NAICS', 515210, 'Cable and Other Subscription Programming', 5, 1451),
(1462, 'NAICS', 5179, 'Other Telecommunications', 3, 1452),
(1456, 'NAICS', 5172, 'Wireless Telecommunications Carriers (except Satellite)', 3, 1452),
(1459, 'NAICS', 5174, 'Satellite Telecommunications', 3, 1452),
(1453, 'NAICS', 5171, 'Wired Telecommunications Carriers', 3, 1452),
(1455, 'NAICS', 51711, 'Wired Telecommunications Carriers', 4, 1453),
(1454, 'NAICS', 517110, 'Wired Telecommunications Carriers', 5, 1455),
(1458, 'NAICS', 51721, 'Wireless Telecommunications Carriers (except Satellite)', 4, 1456),
(1457, 'NAICS', 517210, 'Wireless Telecommunications Carriers (except Satellite)', 5, 1458),
(1461, 'NAICS', 51741, 'Satellite Telecommunications', 4, 1459),
(1460, 'NAICS', 517410, 'Satellite Telecommunications', 5, 1461),
(1463, 'NAICS', 51791, 'Other Telecommunications', 4, 1462),
(1465, 'NAICS', 517919, 'All Other Telecommunications', 5, 1463),
(1464, 'NAICS', 517911, 'Telecommunications Resellers', 5, 1463),
(1467, 'NAICS', 5182, 'Data Processing, Hosting, and Related Services', 3, 1466),
(1469, 'NAICS', 51821, 'Data Processing, Hosting, and Related Services', 4, 1467),
(1468, 'NAICS', 518210, 'Data Processing, Hosting, and Related Services', 5, 1469),
(1471, 'NAICS', 5191, 'Other Information Services', 3, 1470),
(1479, 'NAICS', 51919, 'All Other Information Services', 4, 1471),
(1473, 'NAICS', 51911, 'News Syndicates', 4, 1471),
(1475, 'NAICS', 51912, 'Libraries and Archives', 4, 1471),
(1477, 'NAICS', 51913, 'Internet Publishing and Broadcasting and Web Search Portals', 4, 1471),
(1472, 'NAICS', 519110, 'News Syndicates', 5, 1473),
(1474, 'NAICS', 519120, 'Libraries and Archives', 5, 1475),
(1476, 'NAICS', 519130, 'Internet Publishing and Broadcasting and Web Search Portals', 5, 1477),
(1478, 'NAICS', 519190, 'All Other Information Services', 5, 1479),
(1485, 'NAICS', 522, 'Credit Intermediation and Related Activities', 2, 1480),
(1554, 'NAICS', 525, 'Funds, Trusts, and Other Financial Vehicles', 2, 1480),
(1481, 'NAICS', 521, 'Monetary Authorities-Central Bank', 2, 1480),
(1513, 'NAICS', 523, 'Securities, Commodity Contracts, and Other Financial Investments and Related Activities', 2, 1480),
(1536, 'NAICS', 524, 'Insurance Carriers and Related Activities', 2, 1480),
(1482, 'NAICS', 5211, 'Monetary Authorities-Central Bank', 3, 1481),
(1484, 'NAICS', 52111, 'Monetary Authorities-Central Bank', 4, 1482),
(1483, 'NAICS', 521110, 'Monetary Authorities-Central Bank', 5, 1484),
(1486, 'NAICS', 5221, 'Depository Credit Intermediation', 3, 1485),
(1495, 'NAICS', 5222, 'Nondepository Credit Intermediation', 3, 1485),
(1506, 'NAICS', 5223, 'Activities Related to Credit Intermediation', 3, 1485),
(1488, 'NAICS', 52211, 'Commercial Banking', 4, 1486),
(1492, 'NAICS', 52213, 'Credit Unions', 4, 1486),
(1494, 'NAICS', 52219, 'Other Depository Credit Intermediation', 4, 1486),
(1490, 'NAICS', 52212, 'Savings Institutions', 4, 1486),
(1487, 'NAICS', 522110, 'Commercial Banking', 5, 1488),
(1489, 'NAICS', 522120, 'Savings Institutions', 5, 1490),
(1491, 'NAICS', 522130, 'Credit Unions', 5, 1492),
(1493, 'NAICS', 522190, 'Other Depository Credit Intermediation', 5, 1494),
(1497, 'NAICS', 52221, 'Credit Card Issuing', 4, 1495),
(1499, 'NAICS', 52222, 'Sales Financing', 4, 1495),
(1500, 'NAICS', 52229, 'Other Nondepository Credit Intermediation', 4, 1495),
(1496, 'NAICS', 522210, 'Credit Card Issuing', 5, 1497),
(1498, 'NAICS', 522220, 'Sales Financing', 5, 1499),
(1504, 'NAICS', 522294, 'Secondary Market Financing', 5, 1500),
(1505, 'NAICS', 522298, 'All Other Nondepository Credit Intermediation', 5, 1500),
(1502, 'NAICS', 522292, 'Real Estate Credit', 5, 1500),
(1503, 'NAICS', 522293, 'International Trade Financing', 5, 1500),
(1501, 'NAICS', 522291, 'Consumer Lending', 5, 1500),
(1510, 'NAICS', 52232, 'Financial Transactions Processing, Reserve, and Clearinghouse Activities', 4, 1506),
(1508, 'NAICS', 52231, 'Mortgage and Nonmortgage Loan Brokers', 4, 1506),
(1512, 'NAICS', 52239, 'Other Activities Related to Credit Intermediation', 4, 1506),
(1507, 'NAICS', 522310, 'Mortgage and Nonmortgage Loan Brokers', 5, 1508),
(1509, 'NAICS', 522320, 'Financial Transactions Processing, Reserve, and Clearinghouse Activities', 5, 1510),
(1511, 'NAICS', 522390, 'Other Activities Related to Credit Intermediation', 5, 1512),
(1514, 'NAICS', 5231, 'Securities and Commodity Contracts Intermediation and Brokerage', 3, 1513),
(1526, 'NAICS', 5239, 'Other Financial Investment Activities', 3, 1513),
(1523, 'NAICS', 5232, 'Securities and Commodity Exchanges', 3, 1513),
(1518, 'NAICS', 52312, 'Securities Brokerage', 4, 1514),
(1516, 'NAICS', 52311, 'Investment Banking and Securities Dealing', 4, 1514),
(1520, 'NAICS', 52313, 'Commodity Contracts Dealing', 4, 1514),
(1522, 'NAICS', 52314, 'Commodity Contracts Brokerage', 4, 1514),
(1515, 'NAICS', 523110, 'Investment Banking and Securities Dealing', 5, 1516),
(1519, 'NAICS', 523130, 'Commodity Contracts Dealing', 5, 1520),
(1521, 'NAICS', 523140, 'Commodity Contracts Brokerage', 5, 1522),
(1525, 'NAICS', 52321, 'Securities and Commodity Exchanges', 4, 1523),
(1524, 'NAICS', 523210, 'Securities and Commodity Exchanges', 5, 1525),
(1530, 'NAICS', 52392, 'Portfolio Management', 4, 1526),
(1528, 'NAICS', 52391, 'Miscellaneous Intermediation', 4, 1526),
(1532, 'NAICS', 52393, 'Investment Advice', 4, 1526),
(1533, 'NAICS', 52399, 'All Other Financial Investment Activities', 4, 1526),
(1527, 'NAICS', 523910, 'Miscellaneous Intermediation', 5, 1528),
(1529, 'NAICS', 523920, 'Portfolio Management', 5, 1530),
(1531, 'NAICS', 523930, 'Investment Advice', 5, 1532),
(1535, 'NAICS', 523999, 'Miscellaneous Financial Investment Activities', 5, 1533),
(1534, 'NAICS', 523991, 'Trust, Fiduciary, and Custody Activities', 5, 1533),
(1537, 'NAICS', 5241, 'Insurance Carriers', 3, 1536),
(1547, 'NAICS', 5242, 'Agencies, Brokerages, and Other Insurance Related Activities', 3, 1536),
(1538, 'NAICS', 52411, 'Direct Life, Health, and Medical Insurance Carriers', 4, 1537),
(1546, 'NAICS', 52413, 'Reinsurance Carriers', 4, 1537),
(1541, 'NAICS', 52412, 'Direct Insurance (except Life, Health, and Medical) Carriers', 4, 1537),
(1539, 'NAICS', 524113, 'Direct Life Insurance Carriers', 5, 1538),
(1540, 'NAICS', 524114, 'Direct Health and Medical Insurance Carriers', 5, 1538),
(1920, 'NAICS', 624, 'Social Assistance', 2, 1850),
(1544, 'NAICS', 524128, 'Other Direct Insurance (except Life, Health, and Medical) Carriers', 5, 1541),
(1543, 'NAICS', 524127, 'Direct Title Insurance Carriers', 5, 1541),
(1542, 'NAICS', 524126, 'Direct Property and Casualty Insurance Carriers', 5, 1541),
(1545, 'NAICS', 524130, 'Reinsurance Carriers', 5, 1546),
(1550, 'NAICS', 52429, 'Other Insurance Related Activities', 4, 1547),
(1549, 'NAICS', 52421, 'Insurance Agencies and Brokerages', 4, 1547),
(1548, 'NAICS', 524210, 'Insurance Agencies and Brokerages', 5, 1549),
(1551, 'NAICS', 524291, 'Claims Adjusting', 5, 1550),
(1552, 'NAICS', 524292, 'Third Party Administration of Insurance and Pension Funds', 5, 1550),
(1553, 'NAICS', 524298, 'All Other Insurance Related Activities', 5, 1550),
(1562, 'NAICS', 5259, 'Other Investment Pools and Funds', 3, 1554),
(1555, 'NAICS', 5251, 'Insurance and Employee Benefit Funds', 3, 1554),
(1557, 'NAICS', 52511, 'Pension Funds', 4, 1555),
(1559, 'NAICS', 52512, 'Health and Welfare Funds', 4, 1555),
(1561, 'NAICS', 52519, 'Other Insurance Funds', 4, 1555),
(1556, 'NAICS', 525110, 'Pension Funds', 5, 1557),
(1558, 'NAICS', 525120, 'Health and Welfare Funds', 5, 1559),
(1560, 'NAICS', 525190, 'Other Insurance Funds', 5, 1561),
(1568, 'NAICS', 52599, 'Other Financial Vehicles', 4, 1562),
(1564, 'NAICS', 52591, 'Open-End Investment Funds', 4, 1562),
(1566, 'NAICS', 52592, 'Trusts, Estates, and Agency Accounts', 4, 1562),
(1563, 'NAICS', 525910, 'Open-End Investment Funds', 5, 1564),
(1565, 'NAICS', 525920, 'Trusts, Estates, and Agency Accounts', 5, 1566),
(1567, 'NAICS', 525990, 'Other Financial Vehicles', 5, 1568),
(1620, 'NAICS', 533, 'Lessors of Nonfinancial Intangible Assets (except Copyrighted Works)', 2, 1569),
(1570, 'NAICS', 531, 'Real Estate', 2, 1569),
(1580, 'NAICS', 5312, 'Offices of Real Estate Agents and Brokers', 3, 1570),
(1571, 'NAICS', 5311, 'Lessors of Real Estate', 3, 1570),
(1583, 'NAICS', 5313, 'Activities Related to Real Estate', 3, 1570),
(1575, 'NAICS', 53112, 'Lessors of Nonresidential Buildings (except Miniwarehouses)', 4, 1571),
(1577, 'NAICS', 53113, 'Lessors of Miniwarehouses and Self-Storage Units', 4, 1571),
(1579, 'NAICS', 53119, 'Lessors of Other Real Estate Property', 4, 1571),
(1573, 'NAICS', 53111, 'Lessors of Residential Buildings and Dwellings', 4, 1571),
(1572, 'NAICS', 531110, 'Lessors of Residential Buildings and Dwellings', 5, 1573),
(1574, 'NAICS', 531120, 'Lessors of Nonresidential Buildings (except Miniwarehouses)', 5, 1575),
(1576, 'NAICS', 531130, 'Lessors of Miniwarehouses and Self-Storage Units', 5, 1577),
(1578, 'NAICS', 531190, 'Lessors of Other Real Estate Property', 5, 1579),
(1582, 'NAICS', 53121, 'Offices of Real Estate Agents and Brokers', 4, 1580),
(1581, 'NAICS', 531210, 'Offices of Real Estate Agents and Brokers', 5, 1582),
(1588, 'NAICS', 53132, 'Offices of Real Estate Appraisers', 4, 1583),
(1590, 'NAICS', 53139, 'Other Activities Related to Real Estate', 4, 1583),
(1584, 'NAICS', 53131, 'Real Estate Property Managers', 4, 1583),
(1585, 'NAICS', 531311, 'Residential Property Managers', 5, 1584),
(1586, 'NAICS', 531312, 'Nonresidential Property Managers', 5, 1584),
(1587, 'NAICS', 531320, 'Offices of Real Estate Appraisers', 5, 1588),
(1589, 'NAICS', 531390, 'Other Activities Related to Real Estate', 5, 1590),
(1609, 'NAICS', 5323, 'General Rental Centers', 3, 1591),
(1612, 'NAICS', 5324, 'Commercial and Industrial Machinery and Equipment Rental and Leasing', 3, 1591),
(1592, 'NAICS', 5321, 'Automotive Equipment Rental and Leasing', 3, 1591),
(1598, 'NAICS', 5322, 'Consumer Goods Rental', 3, 1591),
(1597, 'NAICS', 53212, 'Truck, Utility Trailer, and RV (Recreational Vehicle) Rental and Leasing', 4, 1592),
(1593, 'NAICS', 53211, 'Passenger Car Rental and Leasing', 4, 1592),
(1594, 'NAICS', 532111, 'Passenger Car Rental', 5, 1593),
(1595, 'NAICS', 532112, 'Passenger Car Leasing', 5, 1593),
(1596, 'NAICS', 532120, 'Truck, Utility Trailer, and RV (Recreational Vehicle) Rental and Leasing', 5, 1597),
(1604, 'NAICS', 53223, 'Video Tape and Disc Rental', 4, 1598),
(1605, 'NAICS', 53229, 'Other Consumer Goods Rental', 4, 1598),
(1600, 'NAICS', 53221, 'Consumer Electronics and Appliances Rental', 4, 1598),
(1602, 'NAICS', 53222, 'Formal Wear and Costume Rental', 4, 1598),
(1599, 'NAICS', 532210, 'Consumer Electronics and Appliances Rental', 5, 1600),
(1601, 'NAICS', 532220, 'Formal Wear and Costume Rental', 5, 1602),
(1603, 'NAICS', 532230, 'Video Tape and Disc Rental', 5, 1604),
(1608, 'NAICS', 532299, 'All Other Consumer Goods Rental', 5, 1605),
(1607, 'NAICS', 532292, 'Recreational Goods Rental', 5, 1605),
(1606, 'NAICS', 532291, 'Home Health Equipment Rental', 5, 1605),
(1611, 'NAICS', 53231, 'General Rental Centers', 4, 1609),
(1610, 'NAICS', 532310, 'General Rental Centers', 5, 1611),
(1619, 'NAICS', 53249, 'Other Commercial and Industrial Machinery and Equipment Rental and Leasing', 4, 1612),
(1613, 'NAICS', 53241, 'Construction, Transportation, Mining, and Forestry Machinery and Equipment Rental and Leasing', 4, 1612),
(1617, 'NAICS', 53242, 'Office Machinery and Equipment Rental and Leasing', 4, 1612),
(1614, 'NAICS', 532411, 'Commercial Air, Rail, and Water Transportation Equipment Rental and Leasing', 5, 1613),
(1615, 'NAICS', 532412, 'Construction, Mining, and Forestry Machinery and Equipment Rental and Leasing', 5, 1613),
(1616, 'NAICS', 532420, 'Office Machinery and Equipment Rental and Leasing', 5, 1617),
(1618, 'NAICS', 532490, 'Other Commercial and Industrial Machinery and Equipment Rental and Leasing', 5, 1619),
(1621, 'NAICS', 5331, 'Lessors of Nonfinancial Intangible Assets (except Copyrighted Works)', 3, 1620),
(1623, 'NAICS', 53311, 'Lessors of Nonfinancial Intangible Assets (except Copyrighted Works)', 4, 1621),
(1622, 'NAICS', 533110, 'Lessors of Nonfinancial Intangible Assets (except Copyrighted Works)', 5, 1623),
(1625, 'NAICS', 541, 'Professional, Scientific, and Technical Services', 2, 1624),
(1626, 'NAICS', 5411, 'Legal Services', 3, 1625),
(1689, 'NAICS', 5418, 'Advertising, Public Relations, and Related Services', 3, 1625),
(1666, 'NAICS', 5415, 'Computer Systems Design and Related Services', 3, 1625),
(1634, 'NAICS', 5412, 'Accounting, Tax Preparation, Bookkeeping, and Payroll Services', 3, 1625),
(1672, 'NAICS', 5416, 'Management, Scientific, and Technical Consulting Services', 3, 1625),
(1657, 'NAICS', 5414, 'Specialized Design Services', 3, 1625),
(1706, 'NAICS', 5419, 'Other Professional, Scientific, and Technical Services', 3, 1625),
(1683, 'NAICS', 5417, 'Scientific Research and Development Services', 3, 1625),
(1640, 'NAICS', 5413, 'Architectural, Engineering, and Related Services', 3, 1625),
(1631, 'NAICS', 54119, 'Other Legal Services', 4, 1626),
(1628, 'NAICS', 54111, 'Offices of Lawyers', 4, 1626),
(1630, 'NAICS', 54112, 'Offices of Notaries', 4, 1626),
(1627, 'NAICS', 541110, 'Offices of Lawyers', 5, 1628),
(1629, 'NAICS', 541120, 'Offices of Notaries', 5, 1630),
(1632, 'NAICS', 541191, 'Title Abstract and Settlement Offices', 5, 1631),
(1633, 'NAICS', 541199, 'All Other Legal Services', 5, 1631),
(1635, 'NAICS', 54121, 'Accounting, Tax Preparation, Bookkeeping, and Payroll Services', 4, 1634),
(1639, 'NAICS', 541219, 'Other Accounting Services', 5, 1635),
(1638, 'NAICS', 541214, 'Payroll Services', 5, 1635),
(1637, 'NAICS', 541213, 'Tax Preparation Services', 5, 1635),
(1636, 'NAICS', 541211, 'Offices of Certified Public Accountants', 5, 1635),
(1656, 'NAICS', 54138, 'Testing Laboratories', 4, 1640),
(1642, 'NAICS', 54131, 'Architectural Services', 4, 1640),
(1644, 'NAICS', 54132, 'Landscape Architectural Services', 4, 1640),
(1646, 'NAICS', 54133, 'Engineering Services', 4, 1640),
(1648, 'NAICS', 54134, 'Drafting Services', 4, 1640),
(1650, 'NAICS', 54135, 'Building Inspection Services', 4, 1640),
(1652, 'NAICS', 54136, 'Geophysical Surveying and Mapping Services', 4, 1640),
(1654, 'NAICS', 54137, 'Surveying and Mapping (except Geophysical) Services', 4, 1640),
(1641, 'NAICS', 541310, 'Architectural Services', 5, 1642),
(1643, 'NAICS', 541320, 'Landscape Architectural Services', 5, 1644),
(1645, 'NAICS', 541330, 'Engineering Services', 5, 1646),
(1647, 'NAICS', 541340, 'Drafting Services', 5, 1648),
(1649, 'NAICS', 541350, 'Building Inspection Services', 5, 1650),
(1651, 'NAICS', 541360, 'Geophysical Surveying and Mapping Services', 5, 1652),
(1653, 'NAICS', 541370, 'Surveying and Mapping (except Geophysical) Services', 5, 1654),
(1655, 'NAICS', 541380, 'Testing Laboratories', 5, 1656),
(1659, 'NAICS', 54141, 'Interior Design Services', 4, 1657),
(1806, 'NAICS', 56291, 'Remediation Services', 4, 1804),
(1665, 'NAICS', 54149, 'Other Specialized Design Services', 4, 1657),
(1661, 'NAICS', 54142, 'Industrial Design Services', 4, 1657),
(1663, 'NAICS', 54143, 'Graphic Design Services', 4, 1657),
(1658, 'NAICS', 541410, 'Interior Design Services', 5, 1659),
(1660, 'NAICS', 541420, 'Industrial Design Services', 5, 1661),
(1662, 'NAICS', 541430, 'Graphic Design Services', 5, 1663),
(1664, 'NAICS', 541490, 'Other Specialized Design Services', 5, 1665),
(1667, 'NAICS', 54151, 'Computer Systems Design and Related Services', 4, 1666),
(1670, 'NAICS', 541513, 'Computer Facilities Management Services', 5, 1667),
(1668, 'NAICS', 541511, 'Custom Computer Programming Services', 5, 1667),
(1669, 'NAICS', 541512, 'Computer Systems Design Services', 5, 1667),
(1671, 'NAICS', 541519, 'Other Computer Related Services', 5, 1667),
(1682, 'NAICS', 54169, 'Other Scientific and Technical Consulting Services', 4, 1672),
(1673, 'NAICS', 54161, 'Management Consulting Services', 4, 1672),
(1680, 'NAICS', 54162, 'Environmental Consulting Services', 4, 1672),
(1678, 'NAICS', 541618, 'Other Management Consulting Services', 5, 1673),
(1676, 'NAICS', 541613, 'Marketing Consulting Services', 5, 1673),
(1677, 'NAICS', 541614, 'Process, Physical Distribution, and Logistics Consulting Services', 5, 1673),
(1675, 'NAICS', 541612, 'Human Resources Consulting Services', 5, 1673),
(1674, 'NAICS', 541611, 'Administrative Management and General Management Consulting Services', 5, 1673),
(1679, 'NAICS', 541620, 'Environmental Consulting Services', 5, 1680),
(1681, 'NAICS', 541690, 'Other Scientific and Technical Consulting Services', 5, 1682),
(1688, 'NAICS', 54172, 'Research and Development in the Social Sciences and Humanities', 4, 1683),
(1684, 'NAICS', 54171, 'Research and Development in the Physical, Engineering, and Life Sciences', 4, 1683),
(1685, 'NAICS', 541711, 'Research and Development in Biotechnology', 5, 1684),
(1686, 'NAICS', 541712, 'Research and Development in the Physical, Engineering, and Life Sciences (except Biotechnology)', 5, 1684),
(1687, 'NAICS', 541720, 'Research and Development in the Social Sciences and Humanities', 5, 1688),
(1703, 'NAICS', 54187, 'Advertising Material Distribution Services', 4, 1689),
(1705, 'NAICS', 54189, 'Other Services Related to Advertising', 4, 1689),
(1691, 'NAICS', 54181, 'Advertising Agencies', 4, 1689),
(1693, 'NAICS', 54182, 'Public Relations Agencies', 4, 1689),
(1695, 'NAICS', 54183, 'Media Buying Agencies', 4, 1689),
(1697, 'NAICS', 54184, 'Media Representatives', 4, 1689),
(1699, 'NAICS', 54185, 'Outdoor Advertising', 4, 1689),
(1701, 'NAICS', 54186, 'Direct Mail Advertising', 4, 1689),
(1690, 'NAICS', 541810, 'Advertising Agencies', 5, 1691),
(1692, 'NAICS', 541820, 'Public Relations Agencies', 5, 1693),
(1694, 'NAICS', 541830, 'Media Buying Agencies', 5, 1695),
(1696, 'NAICS', 541840, 'Media Representatives', 5, 1697),
(1698, 'NAICS', 541850, 'Outdoor Advertising', 5, 1699),
(1700, 'NAICS', 541860, 'Direct Mail Advertising', 5, 1701),
(1702, 'NAICS', 541870, 'Advertising Material Distribution Services', 5, 1703),
(1704, 'NAICS', 541890, 'Other Services Related to Advertising', 5, 1705),
(1717, 'NAICS', 54199, 'All Other Professional, Scientific, and Technical Services', 4, 1706),
(1708, 'NAICS', 54191, 'Marketing Research and Public Opinion Polling', 4, 1706),
(1709, 'NAICS', 54192, 'Photographic Services', 4, 1706),
(1713, 'NAICS', 54193, 'Translation and Interpretation Services', 4, 1706),
(1715, 'NAICS', 54194, 'Veterinary Services', 4, 1706),
(1707, 'NAICS', 541910, 'Marketing Research and Public Opinion Polling', 5, 1708),
(1710, 'NAICS', 541921, 'Photography Studios, Portrait', 5, 1709),
(1711, 'NAICS', 541922, 'Commercial Photography', 5, 1709),
(1712, 'NAICS', 541930, 'Translation and Interpretation Services', 5, 1713),
(1714, 'NAICS', 541940, 'Veterinary Services', 5, 1715),
(1716, 'NAICS', 541990, 'All Other Professional, Scientific, and Technical Services', 5, 1717),
(1719, 'NAICS', 551, 'Management of Companies and Enterprises', 2, 1718),
(1720, 'NAICS', 5511, 'Management of Companies and Enterprises', 3, 1719),
(1721, 'NAICS', 55111, 'Management of Companies and Enterprises', 4, 1720),
(1722, 'NAICS', 551111, 'Offices of Bank Holding Companies', 5, 1721),
(1723, 'NAICS', 551112, 'Offices of Other Holding Companies', 5, 1721),
(1724, 'NAICS', 551114, 'Corporate, Subsidiary, and Regional Managing Offices', 5, 1721),
(1726, 'NAICS', 561, 'Administrative and Support Services', 2, 1725),
(1792, 'NAICS', 562, 'Waste Management and Remediation Services', 2, 1725),
(1766, 'NAICS', 5616, 'Investigation and Security Services', 3, 1726),
(1785, 'NAICS', 5619, 'Other Support Services', 3, 1726),
(1727, 'NAICS', 5611, 'Office Administrative Services', 3, 1726),
(1758, 'NAICS', 5615, 'Travel Arrangement and Reservation Services', 3, 1726),
(1774, 'NAICS', 5617, 'Services to Buildings and Dwellings', 3, 1726),
(1730, 'NAICS', 5612, 'Facilities Support Services', 3, 1726),
(1733, 'NAICS', 5613, 'Employment Services', 3, 1726),
(1741, 'NAICS', 5614, 'Business Support Services', 3, 1726),
(1729, 'NAICS', 56111, 'Office Administrative Services', 4, 1727),
(1728, 'NAICS', 561110, 'Office Administrative Services', 5, 1729),
(1732, 'NAICS', 56121, 'Facilities Support Services', 4, 1730),
(1731, 'NAICS', 561210, 'Facilities Support Services', 5, 1732),
(1734, 'NAICS', 56131, 'Employment Placement Agencies and Executive Search Services', 4, 1733),
(1740, 'NAICS', 56133, 'Professional Employer Organizations', 4, 1733),
(1738, 'NAICS', 56132, 'Temporary Help Services', 4, 1733),
(1736, 'NAICS', 561312, 'Executive Search Services', 5, 1734),
(1735, 'NAICS', 561311, 'Employment Placement Agencies', 5, 1734),
(1737, 'NAICS', 561320, 'Temporary Help Services', 5, 1738),
(1739, 'NAICS', 561330, 'Professional Employer Organizations', 5, 1740),
(1754, 'NAICS', 56149, 'Other Business Support Services', 4, 1741),
(1743, 'NAICS', 56141, 'Document Preparation Services', 4, 1741),
(1744, 'NAICS', 56142, 'Telephone Call Centers', 4, 1741),
(1747, 'NAICS', 56143, 'Business Service Centers', 4, 1741),
(1751, 'NAICS', 56144, 'Collection Agencies', 4, 1741),
(1753, 'NAICS', 56145, 'Credit Bureaus', 4, 1741),
(1742, 'NAICS', 561410, 'Document Preparation Services', 5, 1743),
(1745, 'NAICS', 561421, 'Telephone Answering Services', 5, 1744),
(1746, 'NAICS', 561422, 'Telemarketing Bureaus and Other Contact Centers', 5, 1744),
(1748, 'NAICS', 561431, 'Private Mail Centers', 5, 1747),
(1749, 'NAICS', 561439, 'Other Business Service Centers (including Copy Shops)', 5, 1747),
(1750, 'NAICS', 561440, 'Collection Agencies', 5, 1751),
(1752, 'NAICS', 561450, 'Credit Bureaus', 5, 1753),
(1757, 'NAICS', 561499, 'All Other Business Support Services', 5, 1754),
(1755, 'NAICS', 561491, 'Repossession Services', 5, 1754),
(1756, 'NAICS', 561492, 'Court Reporting and Stenotype Services', 5, 1754),
(1762, 'NAICS', 56152, 'Tour Operators', 4, 1758),
(1760, 'NAICS', 56151, 'Travel Agencies', 4, 1758),
(1763, 'NAICS', 56159, 'Other Travel Arrangement and Reservation Services', 4, 1758),
(1759, 'NAICS', 561510, 'Travel Agencies', 5, 1760),
(1761, 'NAICS', 561520, 'Tour Operators', 5, 1762),
(1765, 'NAICS', 561599, 'All Other Travel Arrangement and Reservation Services', 5, 1763),
(1764, 'NAICS', 561591, 'Convention and Visitors Bureaus', 5, 1763),
(1767, 'NAICS', 56161, 'Investigation, Guard, and Armored Car Services', 4, 1766),
(1771, 'NAICS', 56162, 'Security Systems Services', 4, 1766),
(1770, 'NAICS', 561613, 'Armored Car Services', 5, 1767),
(1768, 'NAICS', 561611, 'Investigation Services', 5, 1767),
(1769, 'NAICS', 561612, 'Security Guards and Patrol Services', 5, 1767),
(1772, 'NAICS', 561621, 'Security Systems Services (except Locksmiths)', 5, 1771),
(1784, 'NAICS', 56179, 'Other Services to Buildings and Dwellings', 4, 1774),
(1776, 'NAICS', 56171, 'Exterminating and Pest Control Services', 4, 1774),
(1778, 'NAICS', 56172, 'Janitorial Services', 4, 1774),
(1780, 'NAICS', 56173, 'Landscaping Services', 4, 1774),
(1782, 'NAICS', 56174, 'Carpet and Upholstery Cleaning Services', 4, 1774),
(1775, 'NAICS', 561710, 'Exterminating and Pest Control Services', 5, 1776),
(1777, 'NAICS', 561720, 'Janitorial Services', 5, 1778),
(1779, 'NAICS', 561730, 'Landscaping Services', 5, 1780),
(1781, 'NAICS', 561740, 'Carpet and Upholstery Cleaning Services', 5, 1782),
(1783, 'NAICS', 561790, 'Other Services to Buildings and Dwellings', 5, 1784),
(1789, 'NAICS', 56192, 'Convention and Trade Show Organizers', 4, 1785),
(1787, 'NAICS', 56191, 'Packaging and Labeling Services', 4, 1785),
(1791, 'NAICS', 56199, 'All Other Support Services', 4, 1785),
(1786, 'NAICS', 561910, 'Packaging and Labeling Services', 5, 1787),
(1788, 'NAICS', 561920, 'Convention and Trade Show Organizers', 5, 1789),
(1790, 'NAICS', 561990, 'All Other Support Services', 5, 1791),
(1804, 'NAICS', 5629, 'Remediation and Other Waste Management Services', 3, 1792),
(1793, 'NAICS', 5621, 'Waste Collection', 3, 1792),
(1798, 'NAICS', 5622, 'Waste Treatment and Disposal', 3, 1792),
(1794, 'NAICS', 56211, 'Waste Collection', 4, 1793),
(1796, 'NAICS', 562112, 'Hazardous Waste Collection', 5, 1794),
(1797, 'NAICS', 562119, 'Other Waste Collection', 5, 1794),
(1795, 'NAICS', 562111, 'Solid Waste Collection', 5, 1794),
(1799, 'NAICS', 56221, 'Waste Treatment and Disposal', 4, 1798),
(1802, 'NAICS', 562213, 'Solid Waste Combustors and Incinerators', 5, 1799),
(1803, 'NAICS', 562219, 'Other Nonhazardous Waste Treatment and Disposal', 5, 1799),
(1801, 'NAICS', 562212, 'Solid Waste Landfill', 5, 1799),
(1800, 'NAICS', 562211, 'Hazardous Waste Treatment and Disposal', 5, 1799),
(1808, 'NAICS', 56292, 'Materials Recovery Facilities', 4, 1804),
(1809, 'NAICS', 56299, 'All Other Waste Management Services', 4, 1804),
(1805, 'NAICS', 562910, 'Remediation Services', 5, 1806),
(1807, 'NAICS', 562920, 'Materials Recovery Facilities', 5, 1808),
(1811, 'NAICS', 562998, 'All Other Miscellaneous Waste Management Services', 5, 1809),
(1810, 'NAICS', 562991, 'Septic Tank and Related Services', 5, 1809),
(1813, 'NAICS', 611, 'Educational Services', 2, 1812),
(1814, 'NAICS', 6111, 'Elementary and Secondary Schools', 3, 1813),
(1817, 'NAICS', 6112, 'Junior Colleges', 3, 1813),
(1820, 'NAICS', 6113, 'Colleges, Universities, and Professional Schools', 3, 1813),
(1823, 'NAICS', 6114, 'Business Schools and Computer and Management Training', 3, 1813),
(1830, 'NAICS', 6115, 'Technical and Trade Schools', 3, 1813),
(1836, 'NAICS', 6116, 'Other Schools and Instruction', 3, 1813),
(1847, 'NAICS', 6117, 'Educational Support Services', 3, 1813),
(1816, 'NAICS', 61111, 'Elementary and Secondary Schools', 4, 1814),
(1815, 'NAICS', 611110, 'Elementary and Secondary Schools', 5, 1816),
(1819, 'NAICS', 61121, 'Junior Colleges', 4, 1817),
(1818, 'NAICS', 611210, 'Junior Colleges', 5, 1819),
(1822, 'NAICS', 61131, 'Colleges, Universities, and Professional Schools', 4, 1820),
(1821, 'NAICS', 611310, 'Colleges, Universities, and Professional Schools', 5, 1822),
(1827, 'NAICS', 61142, 'Computer Training', 4, 1823),
(1829, 'NAICS', 61143, 'Professional and Management Development Training', 4, 1823),
(1825, 'NAICS', 61141, 'Business and Secretarial Schools', 4, 1823),
(1824, 'NAICS', 611410, 'Business and Secretarial Schools', 5, 1825),
(1826, 'NAICS', 611420, 'Computer Training', 5, 1827),
(1828, 'NAICS', 611430, 'Professional and Management Development Training', 5, 1829),
(1831, 'NAICS', 61151, 'Technical and Trade Schools', 4, 1830),
(1835, 'NAICS', 611519, 'Other Technical and Trade Schools', 5, 1831),
(1834, 'NAICS', 611513, 'Apprenticeship Training', 5, 1831),
(1833, 'NAICS', 611512, 'Flight Training', 5, 1831),
(1832, 'NAICS', 611511, 'Cosmetology and Barber Schools', 5, 1831),
(1838, 'NAICS', 61161, 'Fine Arts Schools', 4, 1836),
(1843, 'NAICS', 61169, 'All Other Schools and Instruction', 4, 1836),
(1842, 'NAICS', 61163, 'Language Schools', 4, 1836),
(1840, 'NAICS', 61162, 'Sports and Recreation Instruction', 4, 1836),
(1837, 'NAICS', 611610, 'Fine Arts Schools', 5, 1838),
(1839, 'NAICS', 611620, 'Sports and Recreation Instruction', 5, 1840),
(1841, 'NAICS', 611630, 'Language Schools', 5, 1842),
(1844, 'NAICS', 611691, 'Exam Preparation and Tutoring', 5, 1843),
(1845, 'NAICS', 611692, 'Automobile Driving Schools', 5, 1843),
(1846, 'NAICS', 611699, 'All Other Miscellaneous Schools and Instruction', 5, 1843),
(1849, 'NAICS', 61171, 'Educational Support Services', 4, 1847),
(1848, 'NAICS', 611710, 'Educational Support Services', 5, 1849),
(1894, 'NAICS', 622, 'Hospitals', 2, 1850),
(1851, 'NAICS', 621, 'Ambulatory Health Care Services', 2, 1850),
(1904, 'NAICS', 623, 'Nursing and Residential Care Facilities', 2, 1850),
(1859, 'NAICS', 6213, 'Offices of Other Health Practitioners', 3, 1851),
(1881, 'NAICS', 6215, 'Medical and Diagnostic Laboratories', 3, 1851),
(1856, 'NAICS', 6212, 'Offices of Dentists', 3, 1851),
(1871, 'NAICS', 6214, 'Outpatient Care Centers', 3, 1851),
(1852, 'NAICS', 6211, 'Offices of Physicians', 3, 1851),
(1885, 'NAICS', 6216, 'Home Health Care Services', 3, 1851),
(1888, 'NAICS', 6219, 'Other Ambulatory Health Care Services', 3, 1851),
(1853, 'NAICS', 62111, 'Offices of Physicians', 4, 1852),
(1855, 'NAICS', 621112, 'Offices of Physicians, Mental Health Specialists', 5, 1853),
(1854, 'NAICS', 621111, 'Offices of Physicians (except Mental Health Specialists)', 5, 1853),
(1858, 'NAICS', 62121, 'Offices of Dentists', 4, 1856),
(1857, 'NAICS', 621210, 'Offices of Dentists', 5, 1858),
(1867, 'NAICS', 62134, 'Offices of Physical, Occupational and Speech Therapists, and Audiologists', 4, 1859),
(1861, 'NAICS', 62131, 'Offices of Chiropractors', 4, 1859),
(1863, 'NAICS', 62132, 'Offices of Optometrists', 4, 1859),
(1865, 'NAICS', 62133, 'Offices of Mental Health Practitioners (except Physicians)', 4, 1859),
(1868, 'NAICS', 62139, 'Offices of All Other Health Practitioners', 4, 1859),
(1860, 'NAICS', 621310, 'Offices of Chiropractors', 5, 1861),
(1862, 'NAICS', 621320, 'Offices of Optometrists', 5, 1863),
(1864, 'NAICS', 621330, 'Offices of Mental Health Practitioners (except Physicians)', 5, 1865),
(1866, 'NAICS', 621340, 'Offices of Physical, Occupational and Speech Therapists, and Audiologists', 5, 1867),
(1870, 'NAICS', 621399, 'Offices of All Other Miscellaneous Health Practitioners', 5, 1868),
(1869, 'NAICS', 621391, 'Offices of Podiatrists', 5, 1868),
(1875, 'NAICS', 62142, 'Outpatient Mental Health and Substance Abuse Centers', 4, 1871),
(1876, 'NAICS', 62149, 'Other Outpatient Care Centers', 4, 1871),
(1873, 'NAICS', 62141, 'Family Planning Centers', 4, 1871),
(1872, 'NAICS', 621410, 'Family Planning Centers', 5, 1873),
(1874, 'NAICS', 621420, 'Outpatient Mental Health and Substance Abuse Centers', 5, 1875),
(1878, 'NAICS', 621492, 'Kidney Dialysis Centers', 5, 1876),
(1880, 'NAICS', 621498, 'All Other Outpatient Care Centers', 5, 1876),
(1877, 'NAICS', 621491, 'HMO Medical Centers', 5, 1876),
(1879, 'NAICS', 621493, 'Freestanding Ambulatory Surgical and Emergency Centers', 5, 1876),
(1882, 'NAICS', 62151, 'Medical and Diagnostic Laboratories', 4, 1881),
(1884, 'NAICS', 621512, 'Diagnostic Imaging Centers', 5, 1882),
(1883, 'NAICS', 621511, 'Medical Laboratories', 5, 1882),
(1887, 'NAICS', 62161, 'Home Health Care Services', 4, 1885),
(1886, 'NAICS', 621610, 'Home Health Care Services', 5, 1887),
(1890, 'NAICS', 62191, 'Ambulance Services', 4, 1888),
(1891, 'NAICS', 62199, 'All Other Ambulatory Health Care Services', 4, 1888),
(1889, 'NAICS', 621910, 'Ambulance Services', 5, 1890),
(1892, 'NAICS', 621991, 'Blood and Organ Banks', 5, 1891),
(1893, 'NAICS', 621999, 'All Other Miscellaneous Ambulatory Health Care Services', 5, 1891),
(1901, 'NAICS', 6223, 'Specialty (except Psychiatric and Substance Abuse) Hospitals', 3, 1894),
(1895, 'NAICS', 6221, 'General Medical and Surgical Hospitals', 3, 1894),
(1898, 'NAICS', 6222, 'Psychiatric and Substance Abuse Hospitals', 3, 1894),
(1897, 'NAICS', 62211, 'General Medical and Surgical Hospitals', 4, 1895),
(1896, 'NAICS', 622110, 'General Medical and Surgical Hospitals', 5, 1897),
(1900, 'NAICS', 62221, 'Psychiatric and Substance Abuse Hospitals', 4, 1898),
(1899, 'NAICS', 622210, 'Psychiatric and Substance Abuse Hospitals', 5, 1900),
(1903, 'NAICS', 62231, 'Specialty (except Psychiatric and Substance Abuse) Hospitals', 4, 1901),
(1902, 'NAICS', 622310, 'Specialty (except Psychiatric and Substance Abuse) Hospitals', 5, 1903),
(1913, 'NAICS', 6233, 'Continuing Care Retirement Communities and Assisted Living Facilities for the Elderly', 3, 1904),
(1908, 'NAICS', 6232, 'Residential Intellectual and Developmental Disability, Mental Health, and Substance Abuse Facilities', 3, 1904),
(1905, 'NAICS', 6231, 'Nursing Care Facilities (Skilled Nursing Facilities)', 3, 1904),
(1917, 'NAICS', 6239, 'Other Residential Care Facilities', 3, 1904),
(1907, 'NAICS', 62311, 'Nursing Care Facilities (Skilled Nursing Facilities)', 4, 1905),
(1906, 'NAICS', 623110, 'Nursing Care Facilities (Skilled Nursing Facilities)', 5, 1907),
(1912, 'NAICS', 62322, 'Residential Mental Health and Substance Abuse Facilities', 4, 1908),
(1910, 'NAICS', 62321, 'Residential Intellectual and Developmental Disability Facilities', 4, 1908),
(1909, 'NAICS', 623210, 'Residential Intellectual and Developmental Disability Facilities', 5, 1910),
(1911, 'NAICS', 623220, 'Residential Mental Health and Substance Abuse Facilities', 5, 1912),
(1914, 'NAICS', 62331, 'Continuing Care Retirement Communities and Assisted Living Facilities for the Elderly', 4, 1913),
(1915, 'NAICS', 623311, 'Continuing Care Retirement Communities', 5, 1914),
(1916, 'NAICS', 623312, 'Assisted Living Facilities for the Elderly', 5, 1914),
(1919, 'NAICS', 62399, 'Other Residential Care Facilities', 4, 1917),
(1918, 'NAICS', 623990, 'Other Residential Care Facilities', 5, 1919),
(1928, 'NAICS', 6242, 'Community Food and Housing, and Emergency and Other Relief Services', 3, 1920),
(1921, 'NAICS', 6241, 'Individual and Family Services', 3, 1920),
(1936, 'NAICS', 6243, 'Vocational Rehabilitation Services', 3, 1920),
(1939, 'NAICS', 6244, 'Child Day Care Services', 3, 1920),
(1927, 'NAICS', 62419, 'Other Individual and Family Services', 4, 1921),
(1923, 'NAICS', 62411, 'Child and Youth Services', 4, 1921),
(2004, 'NAICS', 721, 'Accommodation', 2, 2003),
(1925, 'NAICS', 62412, 'Services for the Elderly and Persons with Disabilities', 4, 1921),
(1922, 'NAICS', 624110, 'Child and Youth Services', 5, 1923),
(1924, 'NAICS', 624120, 'Services for the Elderly and Persons with Disabilities', 5, 1925),
(1926, 'NAICS', 624190, 'Other Individual and Family Services', 5, 1927),
(1931, 'NAICS', 62422, 'Community Housing Services', 4, 1928),
(1935, 'NAICS', 62423, 'Emergency and Other Relief Services', 4, 1928),
(1930, 'NAICS', 62421, 'Community Food Services', 4, 1928),
(1929, 'NAICS', 624210, 'Community Food Services', 5, 1930),
(1932, 'NAICS', 624221, 'Temporary Shelters', 5, 1931),
(1933, 'NAICS', 624229, 'Other Community Housing Services', 5, 1931),
(1934, 'NAICS', 624230, 'Emergency and Other Relief Services', 5, 1935),
(1938, 'NAICS', 62431, 'Vocational Rehabilitation Services', 4, 1936),
(1937, 'NAICS', 624310, 'Vocational Rehabilitation Services', 5, 1938),
(1941, 'NAICS', 62441, 'Child Day Care Services', 4, 1939),
(1940, 'NAICS', 624410, 'Child Day Care Services', 5, 1941),
(1943, 'NAICS', 711, 'Performing Arts, Spectator Sports, and Related Industries', 2, 1942),
(1969, 'NAICS', 712, 'Museums, Historical Sites, and Similar Institutions', 2, 1942),
(1979, 'NAICS', 713, 'Amusement, Gambling, and Recreation Industries', 2, 1942),
(1958, 'NAICS', 7113, 'Promoters of Performing Arts, Sports, and Similar Events', 3, 1943),
(1953, 'NAICS', 7112, 'Spectator Sports', 3, 1943),
(1966, 'NAICS', 7115, 'Independent Artists, Writers, and Performers', 3, 1943),
(1944, 'NAICS', 7111, 'Performing Arts Companies', 3, 1943),
(1963, 'NAICS', 7114, 'Agents and Managers for Artists, Athletes, Entertainers, and Other Public Figures', 3, 1943),
(1948, 'NAICS', 71112, 'Dance Companies', 4, 1944),
(1950, 'NAICS', 71113, 'Musical Groups and Artists', 4, 1944),
(1952, 'NAICS', 71119, 'Other Performing Arts Companies', 4, 1944),
(1946, 'NAICS', 71111, 'Theater Companies and Dinner Theaters', 4, 1944),
(1945, 'NAICS', 711110, 'Theater Companies and Dinner Theaters', 5, 1946),
(1947, 'NAICS', 711120, 'Dance Companies', 5, 1948),
(1949, 'NAICS', 711130, 'Musical Groups and Artists', 5, 1950),
(1951, 'NAICS', 711190, 'Other Performing Arts Companies', 5, 1952),
(1954, 'NAICS', 71121, 'Spectator Sports', 4, 1953),
(1955, 'NAICS', 711211, 'Sports Teams and Clubs', 5, 1954),
(1957, 'NAICS', 711219, 'Other Spectator Sports', 5, 1954),
(1956, 'NAICS', 711212, 'Racetracks', 5, 1954),
(1962, 'NAICS', 71132, 'Promoters of Performing Arts, Sports, and Similar Events without Facilities', 4, 1958),
(1960, 'NAICS', 71131, 'Promoters of Performing Arts, Sports, and Similar Events with Facilities', 4, 1958),
(1959, 'NAICS', 711310, 'Promoters of Performing Arts, Sports, and Similar Events with Facilities', 5, 1960),
(1961, 'NAICS', 711320, 'Promoters of Performing Arts, Sports, and Similar Events without Facilities', 5, 1962),
(1965, 'NAICS', 71141, 'Agents and Managers for Artists, Athletes, Entertainers, and Other Public Figures', 4, 1963),
(1964, 'NAICS', 711410, 'Agents and Managers for Artists, Athletes, Entertainers, and Other Public Figures', 5, 1965),
(1968, 'NAICS', 71151, 'Independent Artists, Writers, and Performers', 4, 1966),
(1967, 'NAICS', 711510, 'Independent Artists, Writers, and Performers', 5, 1968),
(1970, 'NAICS', 7121, 'Museums, Historical Sites, and Similar Institutions', 3, 1969),
(1974, 'NAICS', 71212, 'Historical Sites', 4, 1970),
(1976, 'NAICS', 71213, 'Zoos and Botanical Gardens', 4, 1970),
(1978, 'NAICS', 71219, 'Nature Parks and Other Similar Institutions', 4, 1970),
(1972, 'NAICS', 71211, 'Museums', 4, 1970),
(1971, 'NAICS', 712110, 'Museums', 5, 1972),
(1973, 'NAICS', 712120, 'Historical Sites', 5, 1974),
(1975, 'NAICS', 712130, 'Zoos and Botanical Gardens', 5, 1976),
(1977, 'NAICS', 712190, 'Nature Parks and Other Similar Institutions', 5, 1978),
(1980, 'NAICS', 7131, 'Amusement Parks and Arcades', 3, 1979),
(1985, 'NAICS', 7132, 'Gambling Industries', 3, 1979),
(1990, 'NAICS', 7139, 'Other Amusement and Recreation Industries', 3, 1979),
(1984, 'NAICS', 71312, 'Amusement Arcades', 4, 1980),
(1982, 'NAICS', 71311, 'Amusement and Theme Parks', 4, 1980),
(1981, 'NAICS', 713110, 'Amusement and Theme Parks', 5, 1982),
(1983, 'NAICS', 713120, 'Amusement Arcades', 5, 1984),
(1987, 'NAICS', 71321, 'Casinos (except Casino Hotels)', 4, 1985),
(1989, 'NAICS', 71329, 'Other Gambling Industries', 4, 1985),
(1986, 'NAICS', 713210, 'Casinos (except Casino Hotels)', 5, 1987),
(1988, 'NAICS', 713290, 'Other Gambling Industries', 5, 1989),
(1992, 'NAICS', 71391, 'Golf Courses and Country Clubs', 4, 1990),
(1994, 'NAICS', 71392, 'Skiing Facilities', 4, 1990),
(1996, 'NAICS', 71393, 'Marinas', 4, 1990),
(1998, 'NAICS', 71394, 'Fitness and Recreational Sports Centers', 4, 1990),
(2000, 'NAICS', 71395, 'Bowling Centers', 4, 1990),
(2002, 'NAICS', 71399, 'All Other Amusement and Recreation Industries', 4, 1990),
(1991, 'NAICS', 713910, 'Golf Courses and Country Clubs', 5, 1992),
(1993, 'NAICS', 713920, 'Skiing Facilities', 5, 1994),
(1995, 'NAICS', 713930, 'Marinas', 5, 1996),
(1997, 'NAICS', 713940, 'Fitness and Recreational Sports Centers', 5, 1998),
(1999, 'NAICS', 713950, 'Bowling Centers', 5, 2000),
(2001, 'NAICS', 713990, 'All Other Amusement and Recreation Industries', 5, 2002),
(2020, 'NAICS', 722, 'Food Services and Drinking Places', 2, 2003),
(2005, 'NAICS', 7211, 'Traveler Accommodation', 3, 2004),
(2013, 'NAICS', 7212, 'RV (Recreational Vehicle) Parks and Recreational Camps', 3, 2004),
(2017, 'NAICS', 7213, 'Rooming and Boarding Houses', 3, 2004),
(2010, 'NAICS', 72119, 'Other Traveler Accommodation', 4, 2005),
(2007, 'NAICS', 72111, 'Hotels (except Casino Hotels) and Motels', 4, 2005),
(2009, 'NAICS', 72112, 'Casino Hotels', 4, 2005),
(2006, 'NAICS', 721110, 'Hotels (except Casino Hotels) and Motels', 5, 2007),
(2008, 'NAICS', 721120, 'Casino Hotels', 5, 2009),
(2011, 'NAICS', 721191, 'Bed-and-Breakfast Inns', 5, 2010),
(2012, 'NAICS', 721199, 'All Other Traveler Accommodation', 5, 2010),
(2014, 'NAICS', 72121, 'RV (Recreational Vehicle) Parks and Recreational Camps', 4, 2013),
(2016, 'NAICS', 721214, 'Recreational and Vacation Camps (except Campgrounds)', 5, 2014),
(2015, 'NAICS', 721211, 'RV (Recreational Vehicle) Parks and Campgrounds', 5, 2014),
(2019, 'NAICS', 72131, 'Rooming and Boarding Houses', 4, 2017),
(2018, 'NAICS', 721310, 'Rooming and Boarding Houses', 5, 2019),
(2021, 'NAICS', 7223, 'Special Food Services', 3, 2020),
(2031, 'NAICS', 7225, 'Restaurants and Other Eating Places', 3, 2020),
(2028, 'NAICS', 7224, 'Drinking Places (Alcoholic Beverages)', 3, 2020),
(2023, 'NAICS', 72231, 'Food Service Contractors', 4, 2021),
(2025, 'NAICS', 72232, 'Caterers', 4, 2021),
(2027, 'NAICS', 72233, 'Mobile Food Services', 4, 2021),
(2022, 'NAICS', 722310, 'Food Service Contractors', 5, 2023),
(2024, 'NAICS', 722320, 'Caterers', 5, 2025),
(2026, 'NAICS', 722330, 'Mobile Food Services', 5, 2027),
(2030, 'NAICS', 72241, 'Drinking Places (Alcoholic Beverages)', 4, 2028),
(2029, 'NAICS', 722410, 'Drinking Places (Alcoholic Beverages)', 5, 2030),
(2032, 'NAICS', 72251, 'Restaurants and Other Eating Places', 4, 2031),
(2036, 'NAICS', 722515, 'Snack and Nonalcoholic Beverage Bars', 5, 2032),
(2033, 'NAICS', 722511, 'Full-Service Restaurants', 5, 2032),
(2034, 'NAICS', 722513, 'Limited-Service Restaurants', 5, 2032),
(2035, 'NAICS', 722514, 'Cafeterias, Grill Buffets, and Buffets', 5, 2032),
(2131, 'NAICS', 814, 'Private Households', 2, 2037),
(2103, 'NAICS', 813, 'Religious, Grantmaking, Civic, Professional, and Similar Organizations', 2, 2037),
(2038, 'NAICS', 811, 'Repair and Maintenance', 2, 2037),
(2061, 'NAICS', 8114, 'Personal and Household Goods Repair and Maintenance', 3, 2038),
(2058, 'NAICS', 8113, 'Commercial and Industrial Machinery and Equipment (except Automotive and Electronic) Repair and Maintenance', 3, 2038),
(2052, 'NAICS', 8112, 'Electronic and Precision Equipment Repair and Maintenance', 3, 2038),
(2039, 'NAICS', 8111, 'Automotive Repair and Maintenance', 3, 2038),
(2045, 'NAICS', 81112, 'Automotive Body, Paint, Interior, and Glass Repair', 4, 2039),
(2040, 'NAICS', 81111, 'Automotive Mechanical and Electrical Repair and Maintenance', 4, 2039),
(2048, 'NAICS', 81119, 'Other Automotive Repair and Maintenance', 4, 2039),
(2042, 'NAICS', 811112, 'Automotive Exhaust System Repair', 5, 2040),
(2043, 'NAICS', 811113, 'Automotive Transmission Repair', 5, 2040),
(2041, 'NAICS', 811111, 'General Automotive Repair', 5, 2040),
(2044, 'NAICS', 811118, 'Other Automotive Mechanical and Electrical Repair and Maintenance', 5, 2040),
(2047, 'NAICS', 811122, 'Automotive Glass Replacement Shops', 5, 2045),
(2046, 'NAICS', 811121, 'Automotive Body, Paint, and Interior Repair and Maintenance', 5, 2045),
(2049, 'NAICS', 811191, 'Automotive Oil Change and Lubrication Shops', 5, 2048),
(2050, 'NAICS', 811192, 'Car Washes', 5, 2048),
(2051, 'NAICS', 811198, 'All Other Automotive Repair and Maintenance', 5, 2048),
(2053, 'NAICS', 81121, 'Electronic and Precision Equipment Repair and Maintenance', 4, 2052),
(2057, 'NAICS', 811219, 'Other Electronic and Precision Equipment Repair and Maintenance', 5, 2053),
(2054, 'NAICS', 811211, 'Consumer Electronics Repair and Maintenance', 5, 2053),
(2055, 'NAICS', 811212, 'Computer and Office Machine Repair and Maintenance', 5, 2053),
(2056, 'NAICS', 811213, 'Communication Equipment Repair and Maintenance', 5, 2053),
(2060, 'NAICS', 81131, 'Commercial and Industrial Machinery and Equipment (except Automotive and Electronic) Repair and Maintenance', 4, 2058),
(2059, 'NAICS', 811310, 'Commercial and Industrial Machinery and Equipment (except Automotive and Electronic) Repair and Maintenance', 5, 2060),
(2062, 'NAICS', 81141, 'Home and Garden Equipment and Appliance Repair and Maintenance', 4, 2061),
(2070, 'NAICS', 81149, 'Other Personal and Household Goods Repair and Maintenance', 4, 2061),
(2068, 'NAICS', 81143, 'Footwear and Leather Goods Repair', 4, 2061),
(2066, 'NAICS', 81142, 'Reupholstery and Furniture Repair', 4, 2061),
(2063, 'NAICS', 811411, 'Home and Garden Equipment Repair and Maintenance', 5, 2062),
(2064, 'NAICS', 811412, 'Appliance Repair and Maintenance', 5, 2062),
(2065, 'NAICS', 811420, 'Reupholstery and Furniture Repair', 5, 2066),
(2067, 'NAICS', 811430, 'Footwear and Leather Goods Repair', 5, 2068),
(2069, 'NAICS', 811490, 'Other Personal and Household Goods Repair and Maintenance', 5, 2070),
(2093, 'NAICS', 8129, 'Other Personal Services', 3, 2071),
(2080, 'NAICS', 8122, 'Death Care Services', 3, 2071),
(2072, 'NAICS', 8121, 'Personal Care Services', 3, 2071),
(2085, 'NAICS', 8123, 'Drycleaning and Laundry Services', 3, 2071),
(2077, 'NAICS', 81219, 'Other Personal Care Services', 4, 2072),
(2073, 'NAICS', 81211, 'Hair, Nail, and Skin Care Services', 4, 2072),
(2076, 'NAICS', 812113, 'Nail Salons', 5, 2073),
(2075, 'NAICS', 812112, 'Beauty Salons', 5, 2073),
(2074, 'NAICS', 812111, 'Barber Shops', 5, 2073),
(2078, 'NAICS', 812191, 'Diet and Weight Reducing Centers', 5, 2077),
(2079, 'NAICS', 812199, 'Other Personal Care Services', 5, 2077),
(2082, 'NAICS', 81221, 'Funeral Homes and Funeral Services', 4, 2080),
(2084, 'NAICS', 81222, 'Cemeteries and Crematories', 4, 2080),
(2081, 'NAICS', 812210, 'Funeral Homes and Funeral Services', 5, 2082),
(2083, 'NAICS', 812220, 'Cemeteries and Crematories', 5, 2084),
(2087, 'NAICS', 81231, 'Coin-Operated Laundries and Drycleaners', 4, 2085),
(2090, 'NAICS', 81233, 'Linen and Uniform Supply', 4, 2085),
(2089, 'NAICS', 81232, 'Drycleaning and Laundry Services (except Coin-Operated)', 4, 2085),
(2086, 'NAICS', 812310, 'Coin-Operated Laundries and Drycleaners', 5, 2087),
(2088, 'NAICS', 812320, 'Drycleaning and Laundry Services (except Coin-Operated)', 5, 2089),
(2092, 'NAICS', 812332, 'Industrial Launderers', 5, 2090),
(2091, 'NAICS', 812331, 'Linen Supply', 5, 2090),
(2102, 'NAICS', 81299, 'All Other Personal Services', 4, 2093),
(2100, 'NAICS', 81293, 'Parking Lots and Garages', 4, 2093),
(2096, 'NAICS', 81292, 'Photofinishing', 4, 2093),
(2095, 'NAICS', 81291, 'Pet Care (except Veterinary) Services', 4, 2093),
(2094, 'NAICS', 812910, 'Pet Care (except Veterinary) Services', 5, 2095),
(2098, 'NAICS', 812922, 'One-Hour Photofinishing', 5, 2096),
(2097, 'NAICS', 812921, 'Photofinishing Laboratories (except One-Hour)', 5, 2096),
(2099, 'NAICS', 812930, 'Parking Lots and Garages', 5, 2100),
(2101, 'NAICS', 812990, 'All Other Personal Services', 5, 2102),
(2120, 'NAICS', 8139, 'Business, Professional, Labor, Political, and Similar Organizations', 3, 2103),
(2107, 'NAICS', 8132, 'Grantmaking and Giving Services', 3, 2103),
(2104, 'NAICS', 8131, 'Religious Organizations', 3, 2103),
(2117, 'NAICS', 8134, 'Civic and Social Organizations', 3, 2103),
(2112, 'NAICS', 8133, 'Social Advocacy Organizations', 3, 2103),
(2106, 'NAICS', 81311, 'Religious Organizations', 4, 2104),
(2105, 'NAICS', 813110, 'Religious Organizations', 5, 2106),
(2108, 'NAICS', 81321, 'Grantmaking and Giving Services', 4, 2107),
(2110, 'NAICS', 813212, 'Voluntary Health Organizations', 5, 2108),
(2111, 'NAICS', 813219, 'Other Grantmaking and Giving Services', 5, 2108),
(2109, 'NAICS', 813211, 'Grantmaking Foundations', 5, 2108),
(2113, 'NAICS', 81331, 'Social Advocacy Organizations', 4, 2112),
(2115, 'NAICS', 813312, 'Environment, Conservation and Wildlife Organizations', 5, 2113),
(2114, 'NAICS', 813311, 'Human Rights Organizations', 5, 2113),
(2116, 'NAICS', 813319, 'Other Social Advocacy Organizations', 5, 2113),
(2119, 'NAICS', 81341, 'Civic and Social Organizations', 4, 2117),
(2118, 'NAICS', 813410, 'Civic and Social Organizations', 5, 2119),
(2124, 'NAICS', 81392, 'Professional Organizations', 4, 2120),
(2122, 'NAICS', 81391, 'Business Associations', 4, 2120),
(2130, 'NAICS', 81399, 'Other Similar Organizations (except Business, Professional, Labor, and Political Organizations)', 4, 2120),
(2126, 'NAICS', 81393, 'Labor Unions and Similar Labor Organizations', 4, 2120),
(2128, 'NAICS', 81394, 'Political Organizations', 4, 2120),
(2121, 'NAICS', 813910, 'Business Associations', 5, 2122),
(2123, 'NAICS', 813920, 'Professional Organizations', 5, 2124),
(2125, 'NAICS', 813930, 'Labor Unions and Similar Labor Organizations', 5, 2126),
(2127, 'NAICS', 813940, 'Political Organizations', 5, 2128),
(2129, 'NAICS', 813990, 'Other Similar Organizations (except Business, Professional, Labor, and Political Organizations)', 5, 2130),
(2132, 'NAICS', 8141, 'Private Households', 3, 2131),
(2134, 'NAICS', 81411, 'Private Households', 4, 2132),
(2133, 'NAICS', 814110, 'Private Households', 5, 2134),
(2182, 'NAICS', 925, 'Administration of Housing Programs, Urban Planning, and Community Development', 2, 2135),
(2204, 'NAICS', 928, 'National Security and International Affairs', 2, 2135),
(2200, 'NAICS', 927, 'Space Research and Technology', 2, 2135),
(2188, 'NAICS', 926, 'Administration of Economic Programs', 2, 2135),
(2176, 'NAICS', 924, 'Administration of Environmental Quality Programs', 2, 2135),
(2166, 'NAICS', 923, 'Administration of Human Resource Programs', 2, 2135),
(2136, 'NAICS', 921, 'Executive, Legislative, and Other General Government Support', 2, 2135),
(2150, 'NAICS', 922, 'Justice, Public Order, and Safety Activities', 2, 2135),
(2137, 'NAICS', 9211, 'Executive, Legislative, and Other General Government Support', 3, 2136),
(2149, 'NAICS', 92119, 'Other General Government Support', 4, 2137),
(2143, 'NAICS', 92113, 'Public Finance Activities', 4, 2137),
(2147, 'NAICS', 92115, 'American Indian and Alaska Native Tribal Governments', 4, 2137),
(2141, 'NAICS', 92112, 'Legislative Bodies', 4, 2137),
(2145, 'NAICS', 92114, 'Executive and Legislative Offices, Combined', 4, 2137),
(2139, 'NAICS', 92111, 'Executive Offices', 4, 2137),
(2138, 'NAICS', 921110, 'Executive Offices', 5, 2139),
(2140, 'NAICS', 921120, 'Legislative Bodies', 5, 2141),
(2142, 'NAICS', 921130, 'Public Finance Activities', 5, 2143),
(2144, 'NAICS', 921140, 'Executive and Legislative Offices, Combined', 5, 2145),
(2146, 'NAICS', 921150, 'American Indian and Alaska Native Tribal Governments', 5, 2147),
(2148, 'NAICS', 921190, 'Other General Government Support', 5, 2149),
(2476, 'SEC', 3800, 'INSTRUMENTS & RELATED PRODUCTS', 2, 2791),
(2151, 'NAICS', 9221, 'Justice, Public Order, and Safety Activities', 3, 2150),
(2157, 'NAICS', 92213, 'Legal Counsel and Prosecution', 4, 2151),
(2161, 'NAICS', 92215, 'Parole Offices and Probation Offices', 4, 2151),
(2165, 'NAICS', 92219, 'Other Justice, Public Order, and Safety Activities', 4, 2151),
(2153, 'NAICS', 92211, 'Courts', 4, 2151),
(2155, 'NAICS', 92212, 'Police Protection', 4, 2151),
(2159, 'NAICS', 92214, 'Correctional Institutions', 4, 2151),
(2152, 'NAICS', 922110, 'Courts', 5, 2153),
(2154, 'NAICS', 922120, 'Police Protection', 5, 2155),
(2156, 'NAICS', 922130, 'Legal Counsel and Prosecution', 5, 2157),
(2158, 'NAICS', 922140, 'Correctional Institutions', 5, 2159),
(2160, 'NAICS', 922150, 'Parole Offices and Probation Offices', 5, 2161),
(2162, 'NAICS', 922160, 'Fire Protection', 5, 2163),
(2164, 'NAICS', 922190, 'Other Justice, Public Order, and Safety Activities', 5, 2165),
(2167, 'NAICS', 9231, 'Administration of Human Resource Programs', 3, 2166),
(2173, 'NAICS', 92313, 'Administration of Human Resource Programs (except Education, Public Health, and Veterans'' Affairs Programs)', 4, 2167),
(2169, 'NAICS', 92311, 'Administration of Education Programs', 4, 2167),
(2171, 'NAICS', 92312, 'Administration of Public Health Programs', 4, 2167),
(2175, 'NAICS', 92314, 'Administration of Veterans'' Affairs', 4, 2167),
(2168, 'NAICS', 923110, 'Administration of Education Programs', 5, 2169),
(2170, 'NAICS', 923120, 'Administration of Public Health Programs', 5, 2171),
(2172, 'NAICS', 923130, 'Administration of Human Resource Programs (except Education, Public Health, and Veterans'' Affairs Programs)', 5, 2173),
(2174, 'NAICS', 923140, 'Administration of Veterans'' Affairs', 5, 2175),
(2177, 'NAICS', 9241, 'Administration of Environmental Quality Programs', 3, 2176),
(2179, 'NAICS', 92411, 'Administration of Air and Water Resource and Solid Waste Management Programs', 4, 2177),
(2181, 'NAICS', 92412, 'Administration of Conservation Programs', 4, 2177),
(2178, 'NAICS', 924110, 'Administration of Air and Water Resource and Solid Waste Management Programs', 5, 2179),
(2180, 'NAICS', 924120, 'Administration of Conservation Programs', 5, 2181),
(2183, 'NAICS', 9251, 'Administration of Housing Programs, Urban Planning, and Community Development', 3, 2182),
(2185, 'NAICS', 92511, 'Administration of Housing Programs', 4, 2183),
(2187, 'NAICS', 92512, 'Administration of Urban Planning and Community and Rural Development', 4, 2183),
(2184, 'NAICS', 925110, 'Administration of Housing Programs', 5, 2185),
(2186, 'NAICS', 925120, 'Administration of Urban Planning and Community and Rural Development', 5, 2187),
(2189, 'NAICS', 9261, 'Administration of Economic Program', 3, 2188),
(2193, 'NAICS', 92612, 'Regulation and Administration of Transportation Programs', 4, 2189),
(2199, 'NAICS', 92615, 'Regulation, Licensing, and Inspection of Miscellaneous Commercial Sectors', 4, 2189),
(2197, 'NAICS', 92614, 'Regulation of Agricultural Marketing and Commodities', 4, 2189),
(2195, 'NAICS', 92613, 'Regulation and Administration of Communications, Electric, Gas, and Other Utilities', 4, 2189),
(2191, 'NAICS', 92611, 'Administration of General Economic Programs', 4, 2189),
(2190, 'NAICS', 926110, 'Administration of General Economic Programs', 5, 2191),
(2192, 'NAICS', 926120, 'Regulation and Administration of Transportation Programs', 5, 2193),
(2194, 'NAICS', 926130, 'Regulation and Administration of Communications, Electric, Gas, and Other Utilities', 5, 2195),
(2196, 'NAICS', 926140, 'Regulation of Agricultural Marketing and Commodities', 5, 2197),
(2198, 'NAICS', 926150, 'Regulation, Licensing, and Inspection of Miscellaneous Commercial Sectors', 5, 2199),
(2201, 'NAICS', 9271, 'Space Research and Technology', 3, 2200),
(2203, 'NAICS', 92711, 'Space Research and Technology', 4, 2201),
(2202, 'NAICS', 927110, 'Space Research and Technology', 5, 2203),
(2205, 'NAICS', 9281, 'National Security and International Affairs', 3, 2204),
(2209, 'NAICS', 92812, 'International Affairs', 4, 2205),
(2207, 'NAICS', 92811, 'National Security', 4, 2205),
(2206, 'NAICS', 928110, 'National Security', 5, 2207),
(2208, 'NAICS', 928120, 'International Affairs', 5, 2209),
(2228, 'SEC', 1400, 'NONMETALLIC MINERALS, EXCEPT FUELS', 2, 2789),
(2221, 'SEC', 1300, 'OIL & GAS EXTRACTION', 2, 2789),
(2215, 'SEC', 1000, 'METAL MINING', 2, 2789),
(2918, 'SIC', 1400, 'NONMETALLIC MINERALS, EXCEPT FUELS', 2, 4306),
(2884, 'SIC', 1000, 'METAL MINING', 2, 4306),
(2909, 'SIC', 1300, 'OIL & GAS EXTRACTION', 2, 4306),
(2901, 'SIC', 1200, 'COAL MINING', 2, 4306),
(2234, 'SEC', 1600, 'HEAVY CONSTRUCTION, EXCEPT BUILDING', 2, 2790),
(2229, 'SEC', 1500, 'GENERAL BUILDING CONTRACTORS', 2, 2790),
(2237, 'SEC', 1700, 'SPECIAL TRADE CONTRACTORS', 2, 2790),
(2939, 'SIC', 1500, 'GENERAL BUILDING CONTRACTORS', 2, 4307),
(2955, 'SIC', 1700, 'SPECIAL TRADE CONTRACTORS', 2, 4307),
(2948, 'SIC', 1600, 'HEAVY CONSTRUCTION, EXCEPT BUILDING', 2, 4307),
(2302, 'SEC', 2700, 'PRINTING & PUBLISHING', 2, 2791),
(2292, 'SEC', 2600, 'PAPER & ALLIED PRODUCTS', 2, 2791),
(2283, 'SEC', 2500, 'FURNITURE & FIXTURES', 2, 2791),
(2276, 'SEC', 2400, 'LUMBER & WOOD PRODUCTS', 2, 2791),
(2271, 'SEC', 2300, 'APPAREL & OTHER TEXTILE PRODUCTS', 2, 2791),
(2262, 'SEC', 2200, 'TEXTILE MILL PRODUCTS', 2, 2791),
(2259, 'SEC', 2100, 'TOBACCO PRODUCTS', 2, 2791),
(2240, 'SEC', 2000, 'FOOD & KINDRED PRODUCTS', 2, 2791),
(2500, 'SEC', 3900, 'MISCELLANEOUS MANUFACTURING INDUSTRIES', 2, 2791),
(2337, 'SEC', 2900, 'PETROLEUM & COAL PRODUCTS', 2, 2791),
(2342, 'SEC', 3000, 'RUBBER & MISCELLANEOUS PLASTICS PRODUCTS', 2, 2791),
(2353, 'SEC', 3100, 'LEATHER & ALLIED PRODUCTS', 2, 2791),
(2355, 'SEC', 3200, 'STONE, CLAY & GLASS PRODUCTS', 2, 2791),
(2371, 'SEC', 3300, 'PRIMARY METAL INDUSTRIES', 2, 2791),
(2384, 'SEC', 3400, 'FABRICATED METAL PRODUCTS', 2, 2791),
(2403, 'SEC', 3500, 'INDUSTRIAL MACHINERY & EQUIPMENT', 2, 2791),
(2434, 'SEC', 3600, 'ELECTRONIC & OTHER ELECTRIC INDUSTRIES', 2, 2791),
(2458, 'SEC', 3700, 'TRANSPORTATION EQUIPMENT', 2, 2791),
(2319, 'SEC', 2800, 'CHEMICALS & ALLIED PRODUCTS', 2, 2791),
(3190, 'SIC', 2700, 'PRINTING & PUBLISHING', 2, 4308),
(3124, 'SIC', 2400, 'LUMBER & WOOD PRODUCTS', 2, 4308),
(3083, 'SIC', 2300, 'APPAREL & OTHER TEXTILE PRODUCTS', 2, 4308),
(3050, 'SIC', 2200, 'TEXTILE MILL PRODUCTS', 2, 4308),
(3041, 'SIC', 2100, 'TOBACCO PRODUCTS', 2, 4308),
(2982, 'SIC', 2000, 'FOOD & KINDRED PRODUCTS', 2, 4308),
(3526, 'SIC', 3700, 'TRANSPORTATION EQUIPMENT', 2, 4308),
(3282, 'SIC', 3100, 'LEATHER & ALLIED PRODUCTS', 2, 4308),
(3576, 'SIC', 3900, 'MISCELLANEOUS MANUFACTURING INDUSTRIES', 2, 4308),
(3552, 'SIC', 3800, 'INSTRUMENTS & RELATED PRODUCTS', 2, 4308),
(3480, 'SIC', 3600, 'ELECTRONIC & OTHER ELECTRIC INDUSTRIES', 2, 4308),
(3419, 'SIC', 3500, 'INDUSTRIAL MACHINERY & EQUIPMENT', 2, 4308),
(3371, 'SIC', 3400, 'FABRICATED METAL PRODUCTS', 2, 4308),
(3337, 'SIC', 3300, 'PRIMARY METAL INDUSTRIES', 2, 4308),
(3301, 'SIC', 3200, 'STONE, CLAY & GLASS PRODUCTS', 2, 4308),
(3261, 'SIC', 3000, 'RUBBER & MISCELLANEOUS PLASTICS PRODUCTS', 2, 4308),
(3252, 'SIC', 2900, 'PETROLEUM & COAL PRODUCTS', 2, 4308),
(3214, 'SIC', 2800, 'CHEMICALS & ALLIED PRODUCTS', 2, 4308),
(3167, 'SIC', 2600, 'PAPER & ALLIED PRODUCTS', 2, 4308),
(3148, 'SIC', 2500, 'FURNITURE & FIXTURES', 2, 4308),
(2512, 'SEC', 4000, 'RAILROAD TRANSPORTATION', 2, 2792),
(2516, 'SEC', 4100, 'LOCAL & INTERURBAN PASSENGER TRANSIT', 2, 2792),
(2552, 'SEC', 4900, 'ELECTRIC, GAS & SANITARY SERVICES', 2, 2792),
(2539, 'SEC', 4800, 'COMMUNICATIONS', 2, 2792),
(2536, 'SEC', 4700, 'TRANSPORTATION SERVICES', 2, 2792),
(2534, 'SEC', 4600, 'PIPELINES, EXCEPT NATURAL GAS', 2, 2792),
(2526, 'SEC', 4500, 'TRANSPORT BY AIR', 2, 2792),
(2523, 'SEC', 4400, 'WATER TRANSPORTATION', 2, 2792),
(2517, 'SEC', 4200, 'TRUCKING & WAREHOUSING', 2, 2792),
(3633, 'SIC', 4300, 'US POSTAL SERVICE', 2, 4309),
(3620, 'SIC', 4200, 'TRUCKING & WAREHOUSING', 2, 4309),
(3601, 'SIC', 4000, 'RAILROAD TRANSPORTATION', 2, 4309),
(3605, 'SIC', 4100, 'LOCAL & INTERURBAN PASSENGER TRANSIT', 2, 4309),
(3693, 'SIC', 4900, 'ELECTRIC, GAS & SANITARY SERVICES', 2, 4309),
(3680, 'SIC', 4800, 'COMMUNICATIONS', 2, 4309),
(3667, 'SIC', 4700, 'TRANSPORTATION SERVICES', 2, 4309),
(3662, 'SIC', 4600, 'PIPELINES, EXCEPT NATURAL GAS', 2, 4309),
(3654, 'SIC', 4500, 'TRANSPORT BY AIR', 2, 4309),
(3636, 'SIC', 4400, 'WATER TRANSPORTATION', 2, 4309),
(2568, 'SEC', 5000, 'WHOLESALE TRADE - DURABLE GOODS', 2, 2793),
(2591, 'SEC', 5100, 'WHOLESALE TRADE - NONDURABLE GOODS', 2, 2793),
(3762, 'SIC', 5100, 'WHOLESALE TRADE - NONDURABLE GOODS', 2, 4310),
(3715, 'SIC', 5000, 'WHOLESALE TRADE - DURABLE GOODS', 2, 4310),
(2670, 'SEC', 6200, 'SECURITY & COMMODITY BROKERS', 2, 2795),
(2620, 'SEC', 5500, 'AUTOMOTIVE DEALERS & SERVICE STATIONS', 2, 2794),
(2623, 'SEC', 5600, 'APPAREL & ACCESSORY STORES', 2, 2794),
(2617, 'SEC', 5400, 'FOOD STORES', 2, 2794),
(2605, 'SEC', 5200, 'BUILDING MATERIALS & GARDEN SUPPLIES', 2, 2794),
(2610, 'SEC', 5300, 'GENERAL MERCHANDISE STORES', 2, 2794),
(2630, 'SEC', 5700, 'FURNITURE & HOMEFURNISHING STORES', 2, 2794),
(2637, 'SEC', 5800, 'EATING & DRINKING PLACES', 2, 2794),
(2640, 'SEC', 5900, 'MISCELLANEOUS RETAIL', 2, 2794),
(3837, 'SIC', 5500, 'AUTOMOTIVE DEALERS & SERVICE STATIONS', 2, 4311),
(3854, 'SIC', 5600, 'APPAREL & ACCESSORY STORES', 2, 4311),
(3882, 'SIC', 5800, 'EATING & DRINKING PLACES', 2, 4311),
(3869, 'SIC', 5700, 'FURNITURE & HOMEFURNISHING STORES', 2, 4311),
(3886, 'SIC', 5900, 'MISCELLANEOUS RETAIL', 2, 4311),
(3804, 'SIC', 5200, 'BUILDING MATERIALS & GARDEN SUPPLIES', 2, 4311),
(3815, 'SIC', 5300, 'GENERAL MERCHANDISE STORES', 2, 4311),
(3822, 'SIC', 5400, 'FOOD STORES', 2, 4311),
(2649, 'SEC', 6000, 'DEPOSITORY INSTITUTIONS', 2, 2795),
(2677, 'SEC', 6300, 'INSURANCE CARRIERS', 2, 2795),
(2691, 'SEC', 6400, 'INSURANCE AGENTS, BROKERS & SERVICE', 2, 2795),
(2659, 'SEC', 6100, 'NONDEPOSITORY INSTITUTIONS', 2, 2795),
(2703, 'SEC', 6700, 'HOLDING & OTHER INVESTMENT OFFICES', 2, 2795),
(2694, 'SEC', 6500, 'REAL ESTATE', 2, 2795),
(3948, 'SIC', 6200, 'SECURITY & COMMODITY BROKERS', 2, 4312),
(3937, 'SIC', 6100, 'NONDEPOSITORY INSTITUTIONS', 2, 4312),
(3917, 'SIC', 6000, 'DEPOSITORY INSTITUTIONS', 2, 4312),
(3992, 'SIC', 6700, 'HOLDING & OTHER INVESTMENT OFFICES', 2, 4312),
(3977, 'SIC', 6500, 'REAL ESTATE', 2, 4312),
(3974, 'SIC', 6400, 'INSURANCE AGENTS, BROKERS & SERVICE', 2, 4312),
(3958, 'SIC', 6300, 'INSURANCE CARRIERS', 2, 4312),
(2766, 'SEC', 8100, 'LEGAL SERVICES', 2, 2796),
(2712, 'SEC', 7200, 'PERSONAL SERVICES', 2, 2796),
(2713, 'SEC', 7300, 'BUSINESS SERVICES', 2, 2796),
(2735, 'SEC', 7500, 'AUTO REPAIR, SERVICES & PARKING', 2, 2796),
(2737, 'SEC', 7600, 'MISCELLANEOUS REPAIR SERVICES', 2, 2796),
(2738, 'SEC', 7800, 'MOTION PICTURES', 2, 2796),
(2769, 'SEC', 8200, 'EDUCATIONAL SERVICES', 2, 2796),
(2770, 'SEC', 8300, 'SOCIAL SERVICES', 2, 2796),
(2773, 'SEC', 8600, 'MEMBERSHIP ORGANIZATIONS', 2, 2796),
(2774, 'SEC', 8700, 'ENGINEERING & MANAGEMENT SERVICES', 2, 2796),
(2784, 'SEC', 8900, 'SERVICES, NEC', 2, 2796),
(2748, 'SEC', 7900, 'AMUSEMENT & RECREATIONAL SERVICES', 2, 2796),
(2753, 'SEC', 8000, 'HEALTH SERVICE', 2, 2796),
(2709, 'SEC', 7000, 'HOTELS & OTHER LODGING PLACES', 2, 2796),
(4203, 'SIC', 8400, 'MUSEUMS, BOTANICAL, ZOOLOGICAL GARDENS', 2, 4313),
(4244, 'SIC', 8900, 'SERVICES, NEC', 2, 4313),
(4241, 'SIC', 8800, 'PRIVATE HOUSEHOLDS', 2, 4313),
(4223, 'SIC', 8700, 'ENGINEERING & MANAGEMENT SERVICES', 2, 4313),
(4208, 'SIC', 8600, 'MEMBERSHIP ORGANIZATIONS', 2, 4313),
(4007, 'SIC', 7000, 'HOTELS & OTHER LODGING PLACES', 2, 4313),
(4017, 'SIC', 7200, 'PERSONAL SERVICES', 2, 4313),
(4040, 'SIC', 7300, 'BUSINESS SERVICES', 2, 4313),
(4081, 'SIC', 7500, 'AUTO REPAIR, SERVICES & PARKING', 2, 4313),
(4100, 'SIC', 7600, 'MISCELLANEOUS REPAIR SERVICES', 2, 4313),
(4113, 'SIC', 7800, 'MOTION PICTURES', 2, 4313),
(4125, 'SIC', 7900, 'AMUSEMENT & RECREATIONAL SERVICES', 2, 4313),
(4146, 'SIC', 8000, 'HEALTH SERVICE', 2, 4313),
(4175, 'SIC', 8100, 'LEGAL SERVICES', 2, 4313),
(4178, 'SIC', 8200, 'EDUCATIONAL SERVICES', 2, 4313),
(4192, 'SIC', 8300, 'SOCIAL SERVICES', 2, 4313),
(2785, 'SEC', 9700, 'NATIONAL SECURITY & INTL. AFFAIRS', 2, 2797),
(4256, 'SIC', 9200, 'JUSTICE, PUBLIC ORDER & SAFETY', 2, 4314),
(4277, 'SIC', 9500, 'ENVIRONMENTAL QUALITY & HOUSING', 2, 4314),
(4247, 'SIC', 9100, 'EXECUTIVE, LEGISLATIVE & GENERAL', 2, 4314),
(4265, 'SIC', 9300, 'FINANCE, TAXATION & MONETARY POLICY', 2, 4314),
(4302, 'SIC', 9900, 'NONCLASSIFIABLE ESTABLISHMENTS', 2, 4314),
(4268, 'SIC', 9400, 'ADMINISTRATION OF HUMAN RESOURCES', 2, 4314),
(4297, 'SIC', 9700, 'NATIONAL SECURITY & INTL. AFFAIRS', 2, 4314),
(4284, 'SIC', 9600, 'ADMINISTRATION OF ECONOMIC PROGRAMS', 2, 4314),
(2845, 'SIC', 290, 'General Farms, Primarily Animal', 3, 2825),
(2826, 'SIC', 210, 'Livestock, Except Dairy & Poultry', 3, 2825),
(2840, 'SIC', 270, 'Animal Specialties', 3, 2825),
(2832, 'SIC', 240, 'Dairy Farms', 3, 2825),
(2834, 'SIC', 250, 'Poultry & Eggs', 3, 2825),
(2855, 'SIC', 740, 'Veterinary Services', 3, 2847),
(2864, 'SIC', 780, 'Landscape & Horticultural Services', 3, 2847),
(2861, 'SIC', 760, 'Farm Labor & Management Services', 3, 2847),
(2850, 'SIC', 720, 'Crop Services', 3, 2847),
(2848, 'SIC', 710, 'Soil Preparation Services', 3, 2847),
(2858, 'SIC', 750, 'Animal Services, Except Veterinary', 3, 2847),
(2871, 'SIC', 830, 'Forest Products', 3, 2868),
(2869, 'SIC', 810, 'Timber Tracts', 3, 2868),
(2873, 'SIC', 850, 'Forestry Services', 3, 2868),
(2882, 'SIC', 970, 'Hunting, Trapping & Game Propagation', 3, 2875),
(2880, 'SIC', 920, 'Fish Hatcheries & Preserves', 3, 2875),
(2876, 'SIC', 910, 'Commercial Fishing', 3, 2875),
(2216, 'SEC', 1040, 'Gold & Silver Ores', 3, 2215),
(2217, 'SEC', 1090, 'Miscellaneous Metal Ores', 3, 2215),
(2891, 'SIC', 1040, 'Gold & Silver Ores', 3, 2884),
(2898, 'SIC', 1090, 'Miscellaneous Metal Ores', 3, 2884),
(2889, 'SIC', 1030, 'Lead & Zinc Ores', 3, 2884),
(2885, 'SIC', 1010, 'Iron Ores', 3, 2884),
(2887, 'SIC', 1020, 'Copper Ores', 3, 2884),
(2894, 'SIC', 1060, 'Ferroalloy Ores, Except Vanadium', 3, 2884),
(2896, 'SIC', 1080, 'Metal Mining Services', 3, 2884),
(2219, 'SEC', 1220, 'Bituminous Coal & Lignite Mining', 3, 2218),
(2907, 'SIC', 1240, 'Coal Mining Services', 3, 2901),
(2905, 'SIC', 1230, 'Anthracite Mining', 3, 2901),
(2902, 'SIC', 1220, 'Bituminous Coal & Lignite Mining', 3, 2901),
(2224, 'SEC', 1380, 'Oil & Gas Field Services', 3, 2221),
(2222, 'SEC', 1310, 'Crude Petroleum & Natural Gas', 3, 2221),
(2910, 'SIC', 1310, 'Crude Petroleum & Natural Gas', 3, 2909),
(2914, 'SIC', 1380, 'Oil & Gas Field Services', 3, 2909),
(2912, 'SIC', 1320, 'Natural Gas Liquids', 3, 2909),
(2931, 'SIC', 1470, 'Chemical & Fertilizer Minerals', 3, 2918),
(2935, 'SIC', 1480, 'Nonmetallic Minerals Services', 3, 2918),
(2937, 'SIC', 1490, 'Miscellaneous Nonmetallic Minerals', 3, 2918),
(2919, 'SIC', 1410, 'Dimension Stone', 3, 2918),
(2921, 'SIC', 1420, 'Crushed & Broken Stone', 3, 2918),
(2925, 'SIC', 1440, 'Sand & Gravel', 3, 2918),
(2928, 'SIC', 1450, 'Clay, Ceramic & Refractory Minerals', 3, 2918),
(2230, 'SEC', 1520, 'Residential Building Construction', 3, 2229),
(2231, 'SEC', 1530, 'Operative Builders', 3, 2229),
(2233, 'SEC', 1540, 'Nonresidential Building Construction', 3, 2229),
(2943, 'SIC', 1530, 'Operative Builders', 3, 2939),
(2940, 'SIC', 1520, 'Residential Building Construction', 3, 2939),
(2945, 'SIC', 1540, 'Nonresidential Building Construction', 3, 2939),
(2235, 'SEC', 1620, 'Heavy Construction, Except Highway', 3, 2234),
(2951, 'SIC', 1620, 'Heavy Construction, Except Highway', 3, 2948),
(2949, 'SIC', 1610, 'Highway & Street Construction', 3, 2948),
(2238, 'SEC', 1730, 'Electrical Work', 3, 2237),
(2973, 'SIC', 1780, 'Water Well Drilling', 3, 2955),
(2960, 'SIC', 1730, 'Electrical Work', 3, 2955),
(2966, 'SIC', 1750, 'Carpentry & Floor Work', 3, 2955),
(2969, 'SIC', 1760, 'Roofing, Siding & Sheet Metal Work', 3, 2955),
(2962, 'SIC', 1740, 'Masonry, Stonework & Plastering', 3, 2955),
(2956, 'SIC', 1710, 'Plumbing, Heating, Air-Conditioning', 3, 2955),
(2971, 'SIC', 1770, 'Concrete Work', 3, 2955),
(2975, 'SIC', 1790, 'Miscellaneous Special Trade Contractors', 3, 2955),
(2958, 'SIC', 1720, 'Painting & Paper Hanging', 3, 2955),
(2257, 'SEC', 2090, 'Miscellaneous Food & Kindred Products', 3, 2240),
(2241, 'SEC', 2010, 'Meat Products', 3, 2240),
(2245, 'SEC', 2020, 'Dairy Products', 3, 2240),
(2247, 'SEC', 2030, 'Preserved Fruits & Vegetables', 3, 2240),
(2249, 'SEC', 2040, 'Grain Mill Products', 3, 2240),
(2250, 'SEC', 2050, 'Bakery Products', 3, 2240),
(2252, 'SEC', 2060, 'Sugar & Confectionery Products', 3, 2240),
(2253, 'SEC', 2070, 'Fats & Oils', 3, 2240),
(2254, 'SEC', 2080, 'Beverages', 3, 2240),
(3026, 'SIC', 2080, 'Beverages', 3, 2982),
(3008, 'SIC', 2050, 'Bakery Products', 3, 2982),
(3020, 'SIC', 2070, 'Fats & Oils', 3, 2982),
(2993, 'SIC', 2030, 'Preserved Fruits & Vegetables', 3, 2982),
(2983, 'SIC', 2010, 'Meat Products', 3, 2982),
(2987, 'SIC', 2020, 'Dairy Products', 3, 2982),
(3012, 'SIC', 2060, 'Sugar & Confectionery Products', 3, 2982),
(3033, 'SIC', 2090, 'Miscellaneous Food & Kindred Products', 3, 2982),
(3000, 'SIC', 2040, 'Grain Mill Products', 3, 2982),
(3048, 'SIC', 2140, 'Tobacco Stemming & Redrying', 3, 3041),
(3046, 'SIC', 2130, 'Chewing & Smoking Tobacco', 3, 3041),
(3044, 'SIC', 2120, 'Cigars', 3, 3041),
(3042, 'SIC', 2110, 'Cigarettes', 3, 3041),
(2265, 'SEC', 2220, 'Broadwoven Fabric Mills, Manmade', 3, 2262),
(2267, 'SEC', 2250, 'Knitting Mills', 3, 2262),
(2269, 'SEC', 2270, 'Carpets & Rugs', 3, 2262),
(2263, 'SEC', 2210, 'Broadwoven Fabric Mills, Cotton', 3, 2262),
(3051, 'SIC', 2210, 'Broadwoven Fabric Mills, Cotton', 3, 3050),
(3059, 'SIC', 2250, 'Knitting Mills', 3, 3050),
(3073, 'SIC', 2280, 'Yarn & Thread Mills', 3, 3050),
(3071, 'SIC', 2270, 'Carpets & Rugs', 3, 3050),
(3053, 'SIC', 2220, 'Broadwoven Fabric Mills, Manmade', 3, 3050),
(3057, 'SIC', 2240, 'Narrow Fabric Mills', 3, 3050),
(3077, 'SIC', 2290, 'Miscellaneous Textile Goods', 3, 3050),
(3067, 'SIC', 2260, 'Textile Finishing, Except Wool', 3, 3050),
(3055, 'SIC', 2230, 'Broadwoven Fabric Mills, Wool', 3, 3050),
(2272, 'SEC', 2320, 'Men''s & Boys'' Furnishings', 3, 2271),
(2275, 'SEC', 2390, 'Miscellaneous Fabricated Textile Products', 3, 2271),
(2274, 'SEC', 2340, 'Women''s & Children''s Undergarments', 3, 2271),
(2273, 'SEC', 2330, 'Women''s & Misses'' Outerwear', 3, 2271),
(3115, 'SIC', 2390, 'Miscellaneous Fabricated Textile Products', 3, 3083),
(3098, 'SIC', 2340, 'Women''s & Children''s Undergarments', 3, 3083),
(3084, 'SIC', 2310, 'Men''s & Boys'' Suits & Coats', 3, 3083),
(3086, 'SIC', 2320, 'Men''s & Boys'' Furnishings', 3, 3083),
(3093, 'SIC', 2330, 'Women''s & Misses'' Outerwear', 3, 3083),
(3101, 'SIC', 2350, 'Hats, Caps & Millinery', 3, 3083),
(3103, 'SIC', 2360, 'Girl''s & Children''s Outerwear', 3, 3083),
(3108, 'SIC', 2380, 'Miscellaneous Apparel & Accessories', 3, 3083),
(2280, 'SEC', 2450, 'Wood Buildings & Mobile Homes', 3, 2276),
(2277, 'SEC', 2420, 'Sawmills & Planing Mills', 3, 2276),
(2279, 'SEC', 2430, 'Millwork, Plywood, & Structural Members', 3, 2276),
(3144, 'SIC', 2490, 'Miscellaneous Wood Products', 3, 3124),
(3141, 'SIC', 2450, 'Wood Buildings & Mobile Homes', 3, 3124),
(3137, 'SIC', 2440, 'Wood Containers', 3, 3124),
(3125, 'SIC', 2410, 'Logging', 3, 3124),
(3131, 'SIC', 2430, 'Millwork, Plywood, & Structural Members', 3, 3124),
(2291, 'SEC', 2590, 'Miscellaneous Furniture & Fixtures', 3, 2283),
(2288, 'SEC', 2530, 'Public Building & Related Furniture', 3, 2283),
(2286, 'SEC', 2520, 'Office Furniture', 3, 2283),
(2284, 'SEC', 2510, 'Household Furniture', 3, 2283),
(2290, 'SEC', 2540, 'Partitions & Fixtures', 3, 2283),
(3164, 'SIC', 2590, 'Miscellaneous Furniture & Fixtures', 3, 3148),
(3156, 'SIC', 2520, 'Office Furniture', 3, 3148),
(3149, 'SIC', 2510, 'Household Furniture', 3, 3148),
(3159, 'SIC', 2530, 'Public Building & Related Furniture', 3, 3148),
(3161, 'SIC', 2540, 'Partitions & Fixtures', 3, 3148),
(2297, 'SEC', 2630, 'Paperboard Mills', 3, 2292),
(2299, 'SEC', 2650, 'Paperboard Containers & Boxes', 3, 2292),
(2300, 'SEC', 2670, 'Miscellaneous Converted Paper Products', 3, 2292),
(2293, 'SEC', 2610, 'Pulp Mills', 3, 2292),
(2295, 'SEC', 2620, 'Paper Mills', 3, 2292),
(3180, 'SIC', 2670, 'Miscellaneous Converted Paper Products', 3, 3167),
(3168, 'SIC', 2610, 'Pulp Mills', 3, 3167),
(3174, 'SIC', 2650, 'Paperboard Containers & Boxes', 3, 3167),
(3172, 'SIC', 2630, 'Paperboard Mills', 3, 3167),
(3170, 'SIC', 2620, 'Paper Mills', 3, 3167),
(2317, 'SEC', 2780, 'Blankbooks & Bookbinding', 3, 2302),
(2303, 'SEC', 2710, 'Newspapers', 3, 2302),
(2305, 'SEC', 2720, 'Periodicals', 3, 2302),
(2310, 'SEC', 2740, 'Miscellaneous Publishing', 3, 2302),
(2312, 'SEC', 2750, 'Commercial Printing', 3, 2302),
(2307, 'SEC', 2730, 'Books', 3, 2302),
(2313, 'SEC', 2760, 'Manifold Business Forms', 3, 2302),
(2318, 'SEC', 2790, 'Printing Trade Services', 3, 2302),
(3206, 'SIC', 2770, 'Greeting Cards', 3, 3190),
(3211, 'SIC', 2790, 'Printing Trade Services', 3, 3190),
(3195, 'SIC', 2730, 'Books', 3, 3190),
(3208, 'SIC', 2780, 'Blankbooks & Bookbinding', 3, 3190),
(3191, 'SIC', 2710, 'Newspapers', 3, 3190),
(3193, 'SIC', 2720, 'Periodicals', 3, 3190),
(3198, 'SIC', 2740, 'Miscellaneous Publishing', 3, 3190),
(3200, 'SIC', 2750, 'Commercial Printing', 3, 3190),
(3204, 'SIC', 2760, 'Manifold Business Forms', 3, 3190),
(2321, 'SEC', 2820, 'Plastics Materials & Synthetics', 3, 2319),
(2320, 'SEC', 2810, 'Industrial Inorganic Chemicals', 3, 2319),
(2328, 'SEC', 2840, 'Soap, Cleaners & Toilet Goods', 3, 2319),
(2333, 'SEC', 2860, 'Industrial Organic Chemicals', 3, 2319),
(2335, 'SEC', 2890, 'Miscellaneous Chemical Products', 3, 2319),
(2331, 'SEC', 2850, 'Paints & Allied Products', 3, 2319),
(2334, 'SEC', 2870, 'Agricultural Chemicals', 3, 2319),
(2323, 'SEC', 2830, 'Drugs', 3, 2319),
(3241, 'SIC', 2870, 'Agricultural Chemicals', 3, 3214),
(3235, 'SIC', 2850, 'Paints & Allied Products', 3, 3214),
(3230, 'SIC', 2840, 'Soap, Cleaners & Toilet Goods', 3, 3214),
(3225, 'SIC', 2830, 'Drugs', 3, 3214),
(3215, 'SIC', 2810, 'Industrial Inorganic Chemicals', 3, 3214),
(3246, 'SIC', 2890, 'Miscellaneous Chemical Products', 3, 3214),
(3220, 'SIC', 2820, 'Plastics Materials & Synthetics', 3, 3214),
(3237, 'SIC', 2860, 'Industrial Organic Chemicals', 3, 3214),
(2338, 'SEC', 2910, 'Petroleum Refining', 3, 2337),
(2341, 'SEC', 2990, 'Miscellaneous Petroleum & Coal Products', 3, 2337),
(2340, 'SEC', 2950, 'Asphalt Paving & Roofing Materials', 3, 2337),
(3255, 'SIC', 2950, 'Asphalt Paving & Roofing Materials', 3, 3252),
(3258, 'SIC', 2990, 'Miscellaneous Petroleum & Coal Products', 3, 3252),
(3253, 'SIC', 2910, 'Petroleum Refining', 3, 3252),
(2343, 'SEC', 3010, 'Tires & Inner Tubes', 3, 2342),
(2349, 'SEC', 3080, 'Miscellaneous Plastics Products, nec', 3, 2342),
(2347, 'SEC', 3050, 'Hose & Belting & Gaskets & Packing', 3, 2342),
(2345, 'SEC', 3020, 'Rubber & Plastics Footwear', 3, 2342),
(2348, 'SEC', 3060, 'Fabricated Rubber Products, nec', 3, 2342),
(3269, 'SIC', 3060, 'Fabricated Rubber Products, nec', 3, 3261),
(3266, 'SIC', 3050, 'Hose & Belting & Gaskets & Packing', 3, 3261),
(3262, 'SIC', 3010, 'Tires & Inner Tubes', 3, 3261),
(3272, 'SIC', 3080, 'Miscellaneous Plastics Products, nec', 3, 3261),
(3264, 'SIC', 3020, 'Rubber & Plastics Footwear', 3, 3261),
(2354, 'SEC', 3140, 'Footwear, Except Rubber', 3, 2353),
(3292, 'SIC', 3150, 'Leather Gloves & Mittens', 3, 3282),
(3299, 'SIC', 3190, 'Leather Goods, nec', 3, 3282),
(3294, 'SIC', 3160, 'Luggage', 3, 3282),
(3287, 'SIC', 3140, 'Footwear, Except Rubber', 3, 3282),
(3285, 'SIC', 3130, 'Footwear Cut Stock', 3, 3282),
(3283, 'SIC', 3110, 'Leather Tanning & Finishing', 3, 3282),
(3296, 'SIC', 3170, 'Handbags & Personal Leather Goods', 3, 3282),
(2370, 'SEC', 3290, 'Miscellaneous Nonmetallic Mineral Products', 3, 2355),
(2364, 'SEC', 3250, 'Structural Clay Products', 3, 2355),
(2356, 'SEC', 3210, 'Flat Glass', 3, 2355),
(2358, 'SEC', 3220, 'Glass & Glassware, Pressed or Blown', 3, 2355),
(2360, 'SEC', 3230, 'Products of Purchased Glass', 3, 2355),
(2362, 'SEC', 3240, 'Cement, Hydraulic', 3, 2355),
(2365, 'SEC', 3260, 'Pottery & Related Products', 3, 2355),
(2366, 'SEC', 3270, 'Concrete, Gypsum & Plaster Products', 3, 2355),
(2368, 'SEC', 3280, 'Cut Stone & Stone Products', 3, 2355),
(3311, 'SIC', 3250, 'Structural Clay Products', 3, 3301),
(3309, 'SIC', 3240, 'Cement, Hydraulic', 3, 3301),
(3307, 'SIC', 3230, 'Products of Purchased Glass', 3, 3301),
(3302, 'SIC', 3210, 'Flat Glass', 3, 3301),
(3304, 'SIC', 3220, 'Glass & Glassware, Pressed or Blown', 3, 3301),
(3322, 'SIC', 3270, 'Concrete, Gypsum & Plaster Products', 3, 3301),
(3328, 'SIC', 3280, 'Cut Stone & Stone Products', 3, 3301),
(3330, 'SIC', 3290, 'Miscellaneous Nonmetallic Mineral Products', 3, 3301),
(3316, 'SIC', 3260, 'Pottery & Related Products', 3, 3301),
(2382, 'SEC', 3360, 'Nonferrous Foundries (Castings)', 3, 2371),
(2376, 'SEC', 3330, 'Primary Nonferrous Metals', 3, 2371),
(2375, 'SEC', 3320, 'Iron & Steel Foundries', 3, 2371),
(2372, 'SEC', 3310, 'Blast Furnace & Basic Steel Products', 3, 2371),
(2380, 'SEC', 3350, 'Nonferrous Rolling & Drawing', 3, 2371),
(2383, 'SEC', 3390, 'Miscellaneous Primary Metal Industries', 3, 2371),
(2378, 'SEC', 3340, 'Secondary Nonferrous Metals', 3, 2371),
(3368, 'SIC', 3390, 'Miscellaneous Primary Metal Industries', 3, 3337),
(3362, 'SIC', 3360, 'Nonferrous Foundries (Castings)', 3, 3337),
(3355, 'SIC', 3350, 'Nonferrous Rolling & Drawing', 3, 3337),
(3353, 'SIC', 3340, 'Secondary Nonferrous Metals', 3, 3337),
(3349, 'SIC', 3330, 'Primary Nonferrous Metals', 3, 3337),
(3344, 'SIC', 3320, 'Iron & Steel Foundries', 3, 3337),
(3338, 'SIC', 3310, 'Blast Furnace & Basic Steel Products', 3, 3337),
(2402, 'SEC', 3490, 'Miscellaneous Fabricated Metal Products', 3, 2384),
(2399, 'SEC', 3460, 'Metal Forgings & Stampings', 3, 2384),
(2396, 'SEC', 3450, 'Screw Machine Products, Bolts, Etc.', 3, 2384),
(2391, 'SEC', 3440, 'Fabricated Structural Metal Products', 3, 2384),
(2389, 'SEC', 3430, 'Plumbing & Heating, Except Electric', 3, 2384),
(2388, 'SEC', 3420, 'Cutlery, Handtools & Hardware', 3, 2384),
(2401, 'SEC', 3480, 'Ordnance & Accessories, nec', 3, 2384),
(2385, 'SEC', 3410, 'Metal Cans & Shipping Containers', 3, 2384),
(3380, 'SIC', 3430, 'Plumbing & Heating, Except Electric', 3, 3371),
(3395, 'SIC', 3460, 'Metal Forgings & Stampings', 3, 3371),
(3392, 'SIC', 3450, 'Screw Machine Products, Bolts, Etc.', 3, 3371),
(3372, 'SIC', 3410, 'Metal Cans & Shipping Containers', 3, 3371),
(3375, 'SIC', 3420, 'Cutlery, Handtools & Hardware', 3, 3371),
(3404, 'SIC', 3480, 'Ordnance & Accessories, nec', 3, 3371),
(3401, 'SIC', 3470, 'Metal Services, nec', 3, 3371),
(3384, 'SIC', 3440, 'Fabricated Structural Metal Products', 3, 3371),
(3409, 'SIC', 3490, 'Miscellaneous Fabricated Metal Products', 3, 3371),
(2408, 'SEC', 3530, 'Construction & Related Machinery', 3, 2403),
(2405, 'SEC', 3520, 'Farm & Garden Machinery', 3, 2403),
(2404, 'SEC', 3510, 'Engines & Turbines', 3, 2403),
(2418, 'SEC', 3560, 'General Industry Machinery', 3, 2403),
(2415, 'SEC', 3550, 'Special Industry Machinery', 3, 2403),
(2413, 'SEC', 3540, 'Metalworking Machinery', 3, 2403),
(2424, 'SEC', 3570, 'Computer & Office Equipment', 3, 2403),
(2431, 'SEC', 3580, 'Refrigeration & Service Industry', 3, 2403),
(2433, 'SEC', 3590, 'Industrial Machinery, nec', 3, 2403),
(3434, 'SIC', 3540, 'Metalworking Machinery', 3, 3419),
(3426, 'SIC', 3530, 'Construction & Related Machinery', 3, 3419),
(3474, 'SIC', 3590, 'Industrial Machinery, nec', 3, 3419),
(3468, 'SIC', 3580, 'Refrigeration & Service Industry', 3, 3419),
(3461, 'SIC', 3570, 'Computer & Office Equipment', 3, 3419),
(3451, 'SIC', 3560, 'General Industry Machinery', 3, 3419),
(3444, 'SIC', 3550, 'Special Industry Machinery', 3, 3419),
(3423, 'SIC', 3520, 'Farm & Garden Machinery', 3, 3419),
(2442, 'SEC', 3640, 'Electric Lighting & Wiring Equipment', 3, 2434),
(2443, 'SEC', 3650, 'Household Audio & Video Equipment', 3, 2434),
(2446, 'SEC', 3660, 'Communications Equipment', 3, 2434),
(2440, 'SEC', 3630, 'Household Appliances', 3, 2434),
(2435, 'SEC', 3610, 'Electric Distribution Equipment', 3, 2434),
(2450, 'SEC', 3670, 'Electronic Components & Accessories', 3, 2434),
(2438, 'SEC', 3620, 'Electrical Industrial Apparatus', 3, 2434),
(2456, 'SEC', 3690, 'Miscellaneous Electrical Equipment & Supplies', 3, 2434),
(3484, 'SIC', 3620, 'Electrical Industrial Apparatus', 3, 3480),
(3507, 'SIC', 3660, 'Communications Equipment', 3, 3480),
(3504, 'SIC', 3650, 'Household Audio & Video Equipment', 3, 3480),
(3520, 'SIC', 3690, 'Miscellaneous Electrical Equipment & Supplies', 3, 3480),
(3496, 'SIC', 3640, 'Electric Lighting & Wiring Equipment', 3, 3480),
(3489, 'SIC', 3630, 'Household Appliances', 3, 3480),
(3511, 'SIC', 3670, 'Electronic Components & Accessories', 3, 3480),
(3481, 'SIC', 3610, 'Electric Distribution Equipment', 3, 3480),
(2474, 'SEC', 3760, 'Guided Missiles, Space Vehicles, Parts', 3, 2458),
(2475, 'SEC', 3790, 'Miscellaneous Transportation Equipment', 3, 2458),
(2459, 'SEC', 3710, 'Motor Vehicles & Equipment', 3, 2458),
(2465, 'SEC', 3720, 'Aircraft & Parts', 3, 2458),
(2469, 'SEC', 3730, 'Ship & Boat Building & Repairing', 3, 2458),
(2470, 'SEC', 3740, 'Railroad Equipment', 3, 2458),
(2472, 'SEC', 3750, 'Motorcycles, Bicycles & Parts', 3, 2458),
(3544, 'SIC', 3760, 'Guided Missiles, Space Vehicles, Parts', 3, 3526),
(3537, 'SIC', 3730, 'Ship & Boat Building & Repairing', 3, 3526),
(3533, 'SIC', 3720, 'Aircraft & Parts', 3, 3526),
(3548, 'SIC', 3790, 'Miscellaneous Transportation Equipment', 3, 3526),
(3527, 'SIC', 3710, 'Motor Vehicles & Equipment', 3, 3526),
(3540, 'SIC', 3740, 'Railroad Equipment', 3, 3526),
(3542, 'SIC', 3750, 'Motorcycles, Bicycles & Parts', 3, 3526),
(2479, 'SEC', 3820, 'Measuring & Controlling Devices', 3, 2476),
(2488, 'SEC', 3840, 'Medical Instruments & Supplies', 3, 2476),
(2477, 'SEC', 3810, 'Search & Navigation Equipment', 3, 2476),
(2498, 'SEC', 3870, 'Watches, Clocks, Watchcases & Parts', 3, 2476),
(2494, 'SEC', 3850, 'Ophthalmic Goods', 3, 2476),
(2496, 'SEC', 3860, 'Photographic Equipment & Supplies', 3, 2476),
(3570, 'SIC', 3850, 'Ophthalmic Goods', 3, 3552),
(3564, 'SIC', 3840, 'Medical Instruments & Supplies', 3, 3552),
(3555, 'SIC', 3820, 'Measuring & Controlling Devices', 3, 3552),
(3553, 'SIC', 3810, 'Search & Navigation Equipment', 3, 3552),
(3572, 'SIC', 3860, 'Photographic Equipment & Supplies', 3, 3552),
(3574, 'SIC', 3870, 'Watches, Clocks, Watchcases & Parts', 3, 3552),
(2505, 'SEC', 3940, 'Toys & Sporting Goods', 3, 2500),
(2503, 'SEC', 3930, 'Musical Instruments', 3, 2500),
(2510, 'SEC', 3960, 'Costume Jewelry & Notions', 3, 2500),
(2511, 'SEC', 3990, 'Miscellaneous Manufacturers', 3, 2500),
(2501, 'SEC', 3910, 'Jewelry, Silverware & Plated Ware', 3, 2500),
(2509, 'SEC', 3950, 'Pens, Pencils, Office & Art Supplies', 3, 2500),
(3595, 'SIC', 3990, 'Miscellaneous Manufacturers', 3, 3576),
(3581, 'SIC', 3930, 'Musical Instruments', 3, 3576),
(3577, 'SIC', 3910, 'Jewelry, Silverware & Plated Ware', 3, 3576),
(3583, 'SIC', 3940, 'Toys & Sporting Goods', 3, 3576),
(3587, 'SIC', 3950, 'Pens, Pencils, Office & Art Supplies', 3, 3576),
(3592, 'SIC', 3960, 'Costume Jewelry & Notions', 3, 3576),
(3602, 'SIC', 4010, 'Railroads', 3, 3601),
(3609, 'SIC', 4120, 'Taxicabs', 3, 3605),
(3606, 'SIC', 4110, 'Local & Suburban Transportation', 3, 3605),
(3613, 'SIC', 4140, 'Bus Charter Service', 3, 3605),
(3618, 'SIC', 4170, 'Bus Terminal & Service Facilities', 3, 3605),
(3616, 'SIC', 4150, 'School Buses', 3, 3605),
(3611, 'SIC', 4130, 'Intercity & Rural Bus Transportation', 3, 3605),
(2521, 'SEC', 4230, 'Trucking Terminal Facilities', 3, 2517),
(2520, 'SEC', 4220, 'Public Warehousing & Storage', 3, 2517),
(2518, 'SEC', 4210, 'Trucking & Courier Services, Except Air', 3, 2517),
(3626, 'SIC', 4220, 'Public Warehousing & Storage', 3, 3620),
(3631, 'SIC', 4230, 'Trucking Terminal Facilities', 3, 3620),
(3621, 'SIC', 4210, 'Trucking & Courier Services, Except Air', 3, 3620),
(3634, 'SIC', 4310, 'US Postal Service', 3, 3633),
(2524, 'SEC', 4410, 'Deep Sea Foreign Transport of Freight', 3, 2523),
(3637, 'SIC', 4410, 'Deep Sea Foreign Transport of Freight', 3, 3636),
(3639, 'SIC', 4420, 'Deep Sea Domestic Transport of Freight', 3, 3636),
(3641, 'SIC', 4430, 'Freight Transport on The Great Lakes', 3, 3636),
(3645, 'SIC', 4480, 'Water Transportation of Passengers', 3, 3636),
(3649, 'SIC', 4490, 'Water Transportation Services', 3, 3636),
(3643, 'SIC', 4440, 'Water Transportation of Freight, nec', 3, 3636),
(2527, 'SEC', 4510, 'Air Transportation, Scheduled', 3, 2526),
(2530, 'SEC', 4520, 'Air Transportation, Nonscheduled', 3, 2526),
(2532, 'SEC', 4580, 'Airports, Flying Fields & Services', 3, 2526),
(3660, 'SIC', 4580, 'Airports, Flying Fields & Services', 3, 3654),
(3655, 'SIC', 4510, 'Air Transportation, Scheduled', 3, 3654),
(3658, 'SIC', 4520, 'Air Transportation, Nonscheduled', 3, 3654),
(2535, 'SEC', 4610, 'Pipelines, Except Natural Gas', 3, 2534),
(3663, 'SIC', 4610, 'Pipelines, Except Natural Gas', 3, 3662),
(2537, 'SEC', 4730, 'Freight Transportation Arrangement', 3, 2536),
(3668, 'SIC', 4720, 'Passenger Transportation Arrangement', 3, 3667),
(3674, 'SIC', 4740, 'Rental of Railroad Cars', 3, 3667),
(3676, 'SIC', 4780, 'Miscellaneous Transportation Services', 3, 3667),
(3672, 'SIC', 4730, 'Freight Transportation Arrangement', 3, 3667),
(2548, 'SEC', 4840, 'Cable & Other Pay TV Services', 3, 2539),
(2540, 'SEC', 4810, 'Telephone Communications', 3, 2539),
(2550, 'SEC', 4890, 'Communications Services, nec', 3, 2539),
(2543, 'SEC', 4820, 'Telegraph & Other Communications', 3, 2539),
(2545, 'SEC', 4830, 'Radio & Television Broadcasting', 3, 2539),
(3686, 'SIC', 4830, 'Radio & Television Broadcasting', 3, 3680),
(3689, 'SIC', 4840, 'Cable & Other Pay TV Services', 3, 3680),
(3681, 'SIC', 4810, 'Telephone Communications', 3, 3680),
(3691, 'SIC', 4890, 'Communications Services, nec', 3, 3680),
(3684, 'SIC', 4820, 'Telegraph & Other Communications', 3, 3680),
(2566, 'SEC', 4960, 'Steam & Air Conditioning Supply', 3, 2552),
(2564, 'SEC', 4950, 'Sanitary Services', 3, 2552),
(2562, 'SEC', 4940, 'Water Supply', 3, 2552),
(2559, 'SEC', 4930, 'Combination Utility Services', 3, 2552),
(2555, 'SEC', 4920, 'Gas Production & Distribution', 3, 2552),
(2553, 'SEC', 4910, 'Electric Services', 3, 2552),
(3701, 'SIC', 4930, 'Combination Utility Services', 3, 3693),
(3707, 'SIC', 4950, 'Sanitary Services', 3, 3693),
(3711, 'SIC', 4960, 'Steam & Air Conditioning Supply', 3, 3693),
(3696, 'SIC', 4920, 'Gas Production & Distribution', 3, 3693),
(3694, 'SIC', 4910, 'Electric Services', 3, 3693),
(3713, 'SIC', 4970, 'Irrigation Systems', 3, 3693),
(3705, 'SIC', 4940, 'Water Supply', 3, 3693),
(2583, 'SEC', 5070, 'Hardware, Plumbing & Heating Equipment', 3, 2568),
(2588, 'SEC', 5090, 'Miscellaneous Durable Goods', 3, 2568),
(2569, 'SEC', 5010, 'Motor Vehicles, Parts & Supplies', 3, 2568),
(2579, 'SEC', 5060, 'Electrical Goods', 3, 2568),
(2572, 'SEC', 5030, 'Lumber & Construction Materials', 3, 2568),
(2571, 'SEC', 5020, 'Furniture & Home Furnishings', 3, 2568),
(2577, 'SEC', 5050, 'Metals & Minerals, Except Petroleum', 3, 2568),
(2574, 'SEC', 5040, 'Professional & Commercial Equipment', 3, 2568),
(2585, 'SEC', 5080, 'Machinery Equipment & Supplies', 3, 2568),
(3737, 'SIC', 5050, 'Metals & Minerals, Except Petroleum', 3, 3715),
(3729, 'SIC', 5040, 'Professional & Commercial Equipment', 3, 3715),
(3749, 'SIC', 5080, 'Machinery Equipment & Supplies', 3, 3715),
(3740, 'SIC', 5060, 'Electrical Goods', 3, 3715),
(3721, 'SIC', 5020, 'Furniture & Home Furnishings', 3, 3715),
(3716, 'SIC', 5010, 'Motor Vehicles, Parts & Supplies', 3, 3715),
(3744, 'SIC', 5070, 'Hardware, Plumbing & Heating Equipment', 3, 3715),
(3724, 'SIC', 5030, 'Lumber & Construction Materials', 3, 3715),
(3756, 'SIC', 5090, 'Miscellaneous Durable Goods', 3, 3715),
(2600, 'SEC', 5170, 'Petroleum & Petroleum Products', 3, 2591),
(2598, 'SEC', 5150, 'Farm-Product Raw Materials', 3, 2591),
(2592, 'SEC', 5110, 'Paper & Paper Products', 3, 2591),
(2593, 'SEC', 5120, 'Drugs, Proprietaries & Sundries', 3, 2591),
(2595, 'SEC', 5130, 'Apparel, Piece Goods & Notations', 3, 2591),
(2596, 'SEC', 5140, 'Groceries & Related Products', 3, 2591),
(2599, 'SEC', 5160, 'Chemicals & Allied Products', 3, 2591),
(2604, 'SEC', 5190, 'Miscellaneous Nondurable Goods', 3, 2591),
(2603, 'SEC', 5180, 'Beer, Wine & Distilled Beverages', 3, 2591),
(3769, 'SIC', 5130, 'Apparel, Piece Goods & Notations', 3, 3762),
(3797, 'SIC', 5190, 'Miscellaneous Nondurable Goods', 3, 3762),
(3763, 'SIC', 5110, 'Paper & Paper Products', 3, 3762),
(3784, 'SIC', 5150, 'Farm-Product Raw Materials', 3, 3762),
(3788, 'SIC', 5160, 'Chemicals & Allied Products', 3, 3762),
(3767, 'SIC', 5120, 'Drugs, Proprietaries & Sundries', 3, 3762),
(3774, 'SIC', 5140, 'Groceries & Related Products', 3, 3762),
(3791, 'SIC', 5170, 'Petroleum & Petroleum Products', 3, 3762),
(3794, 'SIC', 5180, 'Beer, Wine & Distilled Beverages', 3, 3762),
(2606, 'SEC', 5210, 'Lumber & Other Building Materials', 3, 2605),
(2608, 'SEC', 5270, 'Mobile Homes Dealers', 3, 2605),
(3813, 'SIC', 5270, 'Mobile Homes Dealers', 3, 3804),
(3807, 'SIC', 5230, 'Paint, Glass & Wallpaper Stores', 3, 3804),
(3809, 'SIC', 5250, 'Hardware Stores', 3, 3804),
(3811, 'SIC', 5260, 'Retail Nurseries & Garden Stores', 3, 3804),
(3805, 'SIC', 5210, 'Lumber & Other Building Materials', 3, 3804),
(2615, 'SEC', 5390, 'Miscellaneous General Merchandise Stores', 3, 2610),
(2613, 'SEC', 5330, 'Variety Stores', 3, 2610),
(2611, 'SEC', 5310, 'Department Stores', 3, 2610),
(3820, 'SIC', 5390, 'Miscellaneous General Merchandise Stores', 3, 3815),
(3818, 'SIC', 5330, 'Variety Stores', 3, 3815),
(3816, 'SIC', 5310, 'Department Stores', 3, 3815),
(2618, 'SEC', 5410, 'Grocery Stores', 3, 2617),
(3833, 'SIC', 5460, 'Retail Bakeries', 3, 3822),
(3831, 'SIC', 5450, 'Dairy Products Stores', 3, 3822),
(3827, 'SIC', 5430, 'Fruit & Vegetable Markets', 3, 3822),
(3829, 'SIC', 5440, 'Candy, Nut & Confectionery Stores', 3, 3822),
(3835, 'SIC', 5490, 'Miscellaneous Food Stores', 3, 3822),
(3823, 'SIC', 5410, 'Grocery Stores', 3, 3822),
(3825, 'SIC', 5420, 'Meat & Fish Markets', 3, 3822),
(2621, 'SEC', 5530, 'Auto & Home Supply Stores', 3, 2620),
(3850, 'SIC', 5570, 'Motorcycle Dealers', 3, 3837),
(3852, 'SIC', 5590, 'Automotive Dealers, nec', 3, 3837),
(3838, 'SIC', 5510, 'New & Used Car Dealers', 3, 3837),
(3842, 'SIC', 5530, 'Auto & Home Supply Stores', 3, 3837),
(3844, 'SIC', 5540, 'Gasoline Service Stations', 3, 3837),
(3846, 'SIC', 5550, 'Boat Dealers', 3, 3837),
(3848, 'SIC', 5560, 'Recreational Vehicle Dealers', 3, 3837),
(2624, 'SEC', 5620, 'Women''s Clothing Stores', 3, 2623),
(2626, 'SEC', 5650, 'Family Clothing Stores', 3, 2623),
(2628, 'SEC', 5660, 'Shoe Stores', 3, 2623),
(3865, 'SIC', 5660, 'Shoe Stores', 3, 3854),
(3857, 'SIC', 5620, 'Women''s Clothing Stores', 3, 3854),
(4254, 'SIC', 9190, 'General Government, nec', 3, 4247),
(3859, 'SIC', 5630, 'Women''s Accessory & Specialty Stores', 3, 3854),
(3861, 'SIC', 5640, 'Children''s & Infants'' Wear Stores', 3, 3854),
(3855, 'SIC', 5610, 'Men''s & Boys'' Clothing Stores', 3, 3854),
(3863, 'SIC', 5650, 'Family Clothing Stores', 3, 3854),
(3867, 'SIC', 5690, 'Miscellaneous Apparel & Accessory Stores', 3, 3854),
(2633, 'SEC', 5730, 'Radio, Television & Computer Stores', 3, 2630),
(2631, 'SEC', 5710, 'Furniture & Homefurnishing Stores', 3, 2630),
(3870, 'SIC', 5710, 'Furniture & Homefurnishing Stores', 3, 3869),
(3877, 'SIC', 5730, 'Radio, Television & Computer Stores', 3, 3869),
(3875, 'SIC', 5720, 'Household Appliance Stores', 3, 3869),
(2638, 'SEC', 5810, 'Eating & Drinking Places', 3, 2637),
(3883, 'SIC', 5810, 'Eating & Drinking Places', 3, 3882),
(2641, 'SEC', 5910, 'Drug Stores & Proprietary Stores', 3, 2640),
(2648, 'SEC', 5990, 'Retail Stores, nec', 3, 2640),
(2643, 'SEC', 5940, 'Miscellaneous Shopping Goods Stores', 3, 2640),
(2646, 'SEC', 5960, 'Nonstore Retailers', 3, 2640),
(3907, 'SIC', 5980, 'Fuel Dealers', 3, 3886),
(3911, 'SIC', 5990, 'Retail Stores, nec', 3, 3886),
(3891, 'SIC', 5930, 'Used Merchandise Stores', 3, 3886),
(3887, 'SIC', 5910, 'Drug Stores & Proprietary Stores', 3, 3886),
(3889, 'SIC', 5920, 'Liquor Stores', 3, 3886),
(3893, 'SIC', 5940, 'Miscellaneous Shopping Goods Stores', 3, 3886),
(3903, 'SIC', 5960, 'Nonstore Retailers', 3, 3886),
(2654, 'SEC', 6030, 'Savings Institutions', 3, 2649),
(2650, 'SEC', 6020, 'Commercial Banks', 3, 2649),
(2657, 'SEC', 6090, 'Functions Closely Related to Banking', 3, 2649),
(3925, 'SIC', 6030, 'Savings Institutions', 3, 3917),
(3921, 'SIC', 6020, 'Commercial Banks', 3, 3917),
(3928, 'SIC', 6060, 'Credit Unions', 3, 3917),
(3934, 'SIC', 6090, 'Functions Closely Related to Banking', 3, 3917),
(3918, 'SIC', 6010, 'Central Reserve Depositories', 3, 3917),
(3931, 'SIC', 6080, 'Foreign Bank & Branches & Agencies', 3, 3917),
(2667, 'SEC', 6160, 'Mortgage Bankers & Brokers', 3, 2659),
(2664, 'SEC', 6150, 'Business Credit Institutions', 3, 2659),
(2662, 'SEC', 6140, 'Personal Credit Unions', 3, 2659),
(2660, 'SEC', 6110, 'Federal & Federally Sponsored Credit Agencies', 3, 2659),
(3942, 'SIC', 6150, 'Business Credit Institutions', 3, 3937),
(3945, 'SIC', 6160, 'Mortgage Bankers & Brokers', 3, 3937),
(3940, 'SIC', 6140, 'Personal Credit Unions', 3, 3937),
(3938, 'SIC', 6110, 'Federal & Federally Sponsored Credit Agencies', 3, 3937),
(2675, 'SEC', 6280, 'Security & Commodity Services', 3, 2670),
(2673, 'SEC', 6220, 'Commodity Contracts Brokers, Dealers', 3, 2670),
(2671, 'SEC', 6210, 'Security Brokers & Dealers', 3, 2670),
(3955, 'SIC', 6280, 'Security & Commodity Services', 3, 3948),
(3949, 'SIC', 6210, 'Security Brokers & Dealers', 3, 3948),
(3951, 'SIC', 6220, 'Commodity Contracts Brokers, Dealers', 3, 3948),
(3953, 'SIC', 6230, 'Security & Commodity Exchanges', 3, 3948),
(2689, 'SEC', 6390, 'Insurance Carriers, nec', 3, 2677),
(2683, 'SEC', 6330, 'Fire, Marine & Casualty Insurance', 3, 2677),
(2680, 'SEC', 6320, 'Medical Service & Health Insurance', 3, 2677),
(2678, 'SEC', 6310, 'Life Insurance', 3, 2677),
(2687, 'SEC', 6360, 'Title Insurance', 3, 2677),
(2685, 'SEC', 6350, 'Surety Insurance', 3, 2677),
(3970, 'SIC', 6370, 'Pension, Health & Welfare Funds', 3, 3958),
(3959, 'SIC', 6310, 'Life Insurance', 3, 3958),
(3961, 'SIC', 6320, 'Medical Service & Health Insurance', 3, 3958),
(3964, 'SIC', 6330, 'Fire, Marine & Casualty Insurance', 3, 3958),
(3966, 'SIC', 6350, 'Surety Insurance', 3, 3958),
(3968, 'SIC', 6360, 'Title Insurance', 3, 3958),
(3972, 'SIC', 6390, 'Insurance Carriers, nec', 3, 3958),
(2692, 'SEC', 6410, 'Insurance Agents, Brokers & Service', 3, 2691),
(3975, 'SIC', 6410, 'Insurance Agents, Brokers & Service', 3, 3974),
(2695, 'SEC', 6510, 'Real Estate Operators & Lessors', 3, 2694),
(2699, 'SEC', 6530, 'Real Estate Agents & Managers', 3, 2694),
(2701, 'SEC', 6550, 'Subdividers & Developers', 3, 2694),
(3989, 'SIC', 6550, 'Subdividers & Developers', 3, 3977),
(3985, 'SIC', 6530, 'Real Estate Agents & Managers', 3, 3977),
(3987, 'SIC', 6540, 'Title Abstract Offices', 3, 3977),
(3978, 'SIC', 6510, 'Real Estate Operators & Lessors', 3, 3977),
(2704, 'SEC', 6790, 'Miscellaneous Investing', 3, 2703),
(3993, 'SIC', 6710, 'Holding Offices', 3, 3992),
(3996, 'SIC', 6720, 'Investment Offices', 3, 3992),
(4002, 'SIC', 6790, 'Miscellaneous Investing', 3, 3992),
(3999, 'SIC', 6730, 'Trusts', 3, 3992),
(2710, 'SEC', 7010, 'Hotels & Motels', 3, 2709),
(4012, 'SIC', 7030, 'Camps & Recreational Vehicle Parks', 3, 4007),
(4015, 'SIC', 7040, 'Membership Basis Organization Hotels', 3, 4007),
(4010, 'SIC', 7020, 'Rooming & Boarding Houses', 3, 4007),
(4008, 'SIC', 7010, 'Hotels & Motels', 3, 4007),
(4037, 'SIC', 7290, 'Miscellaneous Personal Services', 3, 4017),
(4029, 'SIC', 7230, 'Beauty Shops', 3, 4017),
(4033, 'SIC', 7250, 'Shoe Repair & Shoeshine Parlors', 3, 4017),
(4031, 'SIC', 7240, 'Barber Shops', 3, 4017),
(4018, 'SIC', 7210, 'Laundry, Cleaning & Garment Services', 3, 4017),
(4035, 'SIC', 7260, 'Funeral Service & Crematories', 3, 4017),
(4027, 'SIC', 7220, 'Photographic Studios, Portrait', 3, 4017),
(2725, 'SEC', 7370, 'Computer & Data Processing Services', 3, 2713),
(2720, 'SEC', 7350, 'Misc. Equipment Rental & Leasing', 3, 2713),
(2719, 'SEC', 7340, 'Services to Buildings', 3, 2713),
(2717, 'SEC', 7330, 'Mailing, Reproductive, Stenographic', 3, 2713),
(2716, 'SEC', 7320, 'Credit Reporting & Collection', 3, 2713),
(2714, 'SEC', 7310, 'Advertising', 3, 2713),
(2731, 'SEC', 7380, 'Miscellaneous Business Services', 3, 2713),
(2722, 'SEC', 7360, 'Personnel Supply Services', 3, 2713),
(4055, 'SIC', 7340, 'Services to Buildings', 3, 4040),
(4075, 'SIC', 7380, 'Miscellaneous Business Services', 3, 4040),
(4058, 'SIC', 7350, 'Misc. Equipment Rental & Leasing', 3, 4040),
(4049, 'SIC', 7330, 'Mailing, Reproductive, Stenographic', 3, 4040),
(4046, 'SIC', 7320, 'Credit Reporting & Collection', 3, 4040),
(4065, 'SIC', 7370, 'Computer & Data Processing Services', 3, 4040),
(4062, 'SIC', 7360, 'Personnel Supply Services', 3, 4040),
(4041, 'SIC', 7310, 'Advertising', 3, 4040),
(2736, 'SEC', 7510, 'Automotive Rentals, No Drivers', 3, 2735),
(4097, 'SIC', 7540, 'Automotive Services, Except Repair', 3, 4081),
(4087, 'SIC', 7520, 'Automobile Parking', 3, 4081),
(4089, 'SIC', 7530, 'Automotive Repair Shops', 3, 4081),
(4082, 'SIC', 7510, 'Automotive Rentals, No Drivers', 3, 4081),
(4101, 'SIC', 7620, 'Electrical Repair Shops', 3, 4100),
(4109, 'SIC', 7690, 'Miscellaneous Repair Shops', 3, 4100),
(4105, 'SIC', 7630, 'Watch, Clock & Jewelry Repair', 3, 4100),
(4107, 'SIC', 7640, 'Reupholstery & Furniture Repair', 3, 4100),
(2745, 'SEC', 7830, 'Motion Picture Theaters', 3, 2738),
(2746, 'SEC', 7840, 'Video Tape Rental', 3, 2738),
(2742, 'SEC', 7820, 'Motion Picture Distribution & Services', 3, 2738),
(2739, 'SEC', 7810, 'Motion Picture Production & Services', 3, 2738),
(4120, 'SIC', 7830, 'Motion Picture Theaters', 3, 4113),
(4117, 'SIC', 7820, 'Motion Picture Distribution & Services', 3, 4113),
(4114, 'SIC', 7810, 'Motion Picture Production & Services', 3, 4113),
(4123, 'SIC', 7840, 'Video Tape Rental', 3, 4113),
(2749, 'SEC', 7940, 'Commercial Sports', 3, 2748),
(2751, 'SEC', 7990, 'Misc. Amusement & Recreation Services', 3, 2748),
(4128, 'SIC', 7920, 'Producers, Orchestras, Entertainers', 3, 4125),
(4131, 'SIC', 7930, 'Bowling Centers', 3, 4125),
(4133, 'SIC', 7940, 'Commercial Sports', 3, 4125),
(4136, 'SIC', 7950, 'Ski Facilities', 3, 4125),
(4139, 'SIC', 7990, 'Misc. Amusement & Recreation Services', 3, 4125),
(4126, 'SIC', 7910, 'Dance Studios, Schools & Halls', 3, 4125),
(2764, 'SEC', 8090, 'Health & Allied Services, nec', 3, 2753),
(2762, 'SEC', 8080, 'Home Health Care Services', 3, 2753),
(2754, 'SEC', 8010, 'Offices & Clinics of Medical Doctors', 3, 2753),
(2756, 'SEC', 8050, 'Nursing & Personal Care Facilities', 3, 2753),
(2758, 'SEC', 8060, 'Hospitals', 3, 2753),
(2760, 'SEC', 8070, 'Medical & Dental Laboratories', 3, 2753),
(4171, 'SIC', 8090, 'Health & Allied Services, nec', 3, 4146),
(4158, 'SIC', 8050, 'Nursing & Personal Care Facilities', 3, 4146),
(4153, 'SIC', 8040, 'Offices of Other Health Practitioners', 3, 4146),
(4169, 'SIC', 8080, 'Home Health Care Services', 3, 4146),
(4151, 'SIC', 8030, 'Offices of Osteopathic Physicians', 3, 4146),
(4149, 'SIC', 8020, 'Offices & Clinics of Dentists', 3, 4146),
(4166, 'SIC', 8070, 'Medical & Dental Laboratories', 3, 4146),
(4147, 'SIC', 8010, 'Offices & Clinics of Medical Doctors', 3, 4146),
(4162, 'SIC', 8060, 'Hospitals', 3, 4146),
(2767, 'SEC', 8110, 'Legal Services', 3, 2766),
(4176, 'SIC', 8110, 'Legal Services', 3, 4175),
(4179, 'SIC', 8210, 'Elementary & Secondary Schools', 3, 4178),
(4186, 'SIC', 8240, 'Vocational Schools', 3, 4178),
(4181, 'SIC', 8220, 'Colleges & Universities', 3, 4178),
(4190, 'SIC', 8290, 'Schools & Educational Services, nec', 3, 4178),
(4184, 'SIC', 8230, 'Libraries', 3, 4178),
(2771, 'SEC', 8350, 'Child Day Care Services', 3, 2770),
(4193, 'SIC', 8320, 'Individual & Family Services', 3, 4192),
(4197, 'SIC', 8350, 'Child Day Care Services', 3, 4192),
(4201, 'SIC', 8390, 'Social Services, nec', 3, 4192),
(4195, 'SIC', 8330, 'Job Training & Related Services', 3, 4192),
(4199, 'SIC', 8360, 'Residential Care', 3, 4192),
(4204, 'SIC', 8410, 'Museums & Art Galleries', 3, 4203),
(4206, 'SIC', 8420, 'Botanical & Zoological Gardens', 3, 4203),
(4217, 'SIC', 8650, 'Political Organizations', 3, 4208),
(4221, 'SIC', 8690, 'Membership Organizations, nec', 3, 4208),
(4213, 'SIC', 8630, 'Labor Organizations', 3, 4208),
(4209, 'SIC', 8610, 'Business Associations', 3, 4208),
(4211, 'SIC', 8620, 'Professional Organizations', 3, 4208),
(4215, 'SIC', 8640, 'Civic & Social Organizations', 3, 4208),
(4219, 'SIC', 8660, 'Religious Organizations', 3, 4208),
(2780, 'SEC', 8740, 'Management & Public Relations', 3, 2774),
(2775, 'SEC', 8710, 'Engineering & Architectural Services', 3, 2774),
(2777, 'SEC', 8730, 'Research & Testing Services', 3, 2774),
(4228, 'SIC', 8720, 'Accounting, Auditing & Bookkeeping', 3, 4223),
(4235, 'SIC', 8740, 'Management & Public Relations', 3, 4223),
(4224, 'SIC', 8710, 'Engineering & Architectural Services', 3, 4223),
(4230, 'SIC', 8730, 'Research & Testing Services', 3, 4223),
(4242, 'SIC', 8810, 'Private Households', 3, 4241),
(4245, 'SIC', 8990, 'Services, nec', 3, 4244),
(4252, 'SIC', 9130, 'Executive & Legislative Combined', 3, 4247),
(4250, 'SIC', 9120, 'Legislative Bodies', 3, 4247),
(4248, 'SIC', 9110, 'Executive Offices', 3, 4247),
(4259, 'SIC', 9220, 'Public Order & Safety', 3, 4256),
(4266, 'SIC', 9310, 'Finance, Taxation & Monetary Policy', 3, 4265),
(4275, 'SIC', 9450, 'Administration of Veteran''s Affairs', 3, 4268),
(4271, 'SIC', 9430, 'Admin. of Public Health Programs', 3, 4268),
(4273, 'SIC', 9440, 'Admin. of Social & Manpower Programs', 3, 4268),
(4269, 'SIC', 9410, 'Admin. of Educational Programs', 3, 4268),
(4278, 'SIC', 9510, 'Environmental Quality', 3, 4277),
(4281, 'SIC', 9530, 'Housing & Urban Development', 3, 4277),
(4289, 'SIC', 9630, 'Regulation, Admin. of Utilities', 3, 4284),
(4293, 'SIC', 9650, 'Regulation Misc. Commercial Sectors', 3, 4284),
(4295, 'SIC', 9660, 'Space Research & Technology', 3, 4284),
(4287, 'SIC', 9620, 'Regulation, Admin. of Transportation', 3, 4284),
(4285, 'SIC', 9610, 'Administration of General Economic Programs', 3, 4284),
(4291, 'SIC', 9640, 'Regulation of Agricultural Marketing', 3, 4284),
(2786, 'SEC', 9720, 'International Affairs', 3, 2785),
(4300, 'SIC', 9720, 'International Affairs', 3, 4297),
(4298, 'SIC', 9710, 'National Security', 3, 4297),
(4303, 'SIC', 9990, 'Nonclassifiable Establishments', 3, 4302)
RETURNING industry_id;

--
-- Data for Name: industry_level; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO industry_level (industry_level_id, industry_classification, ancestor_id, ancestor_code, ancestor_depth, descendant_id, descendant_code, descendant_depth) VALUES
(1, 'SEC', 2677, 6300, 2, 2689, 6390, 3),
(2, 'NAICS', 1666, 5415, 3, 1671, 541519, 5),
(3, 'NAICS', 931, 423, 2, 999, 42384, 4),
(4, 'SEC', 2791, 20, 1, 2362, 3240, 3),
(5, 'SEC', 2792, 40, 1, 2538, 4731, 4),
(6, 'SIC', 3815, 5300, 2, 3820, 5390, 3),
(7, 'NAICS', 1809, 56299, 4, 1810, 562991, 5),
(8, 'SIC', 4314, 90, 1, 4251, 9121, 4),
(9, 'NAICS', 1612, 5324, 3, 1617, 53242, 4),
(10, 'NAICS', 1868, 62139, 4, 1870, 621399, 5),
(11, 'NAICS', 1026, 4243, 3, 1031, 424330, 5),
(12, 'SIC', 4311, 52, 1, 3890, 5921, 4),
(13, 'NAICS', 1942, 71, 1, 1971, 712110, 5),
(14, 'SIC', 4313, 70, 1, 4067, 7372, 4),
(15, 'SIC', 3474, 3590, 3, 3475, 3592, 4),
(16, 'SIC', 4308, 20, 1, 3275, 3083, 4),
(17, 'NAICS', 2037, 81, 1, 2083, 812220, 5),
(18, 'SIC', 4314, 90, 1, 4254, 9190, 3),
(19, 'SIC', 2834, 250, 3, 2838, 254, 4),
(20, 'NAICS', 56, 112, 2, 93, 11292, 4),
(21, 'NAICS', 1555, 5251, 3, 1561, 52519, 4),
(22, 'SEC', 2384, 3400, 2, 2395, 3448, 4),
(23, 'SIC', 3409, 3490, 3, 3418, 3499, 4),
(24, 'NAICS', 1, 11, 1, 130, 115310, 5),
(25, 'NAICS', 1625, 541, 2, 1629, 541120, 5),
(26, 'SIC', 3050, 2200, 2, 3072, 2273, 4),
(27, 'SIC', 4040, 7300, 2, 4054, 7338, 4),
(28, 'SEC', 2795, 60, 1, 2695, 6510, 3),
(29, 'NAICS', 1431, 5122, 3, 1437, 51223, 4),
(30, 'NAICS', 930, 42, 1, 1088, 42499, 4),
(31, 'NAICS', 1684, 54171, 4, 1686, 541712, 5),
(32, 'NAICS', 1726, 561, 2, 1754, 56149, 4),
(33, 'SIC', 4082, 7510, 3, 4086, 7519, 4),
(34, 'SIC', 3744, 5070, 3, 3745, 5072, 4),
(35, 'SEC', 2795, 60, 1, 2680, 6320, 3),
(36, 'NAICS', 930, 42, 1, 1016, 4241, 3),
(37, 'NAICS', 1792, 562, 2, 1804, 5629, 3),
(38, 'NAICS', 236, 2381, 3, 247, 238160, 5),
(39, 'SEC', 2572, 5030, 3, 2573, 5031, 4),
(40, 'NAICS', 1555, 5251, 3, 1556, 525110, 5),
(41, 'NAICS', 1570, 531, 2, 1574, 531120, 5),
(42, 'SIC', 3246, 2890, 3, 3247, 2891, 4),
(43, 'NAICS', 134, 2111, 3, 137, 211112, 5),
(44, 'NAICS', 1725, 56, 1, 1732, 56121, 4),
(45, 'NAICS', 1972, 71211, 4, 1971, 712110, 5),
(46, 'NAICS', 1624, 54, 1, 1654, 54137, 4),
(47, 'NAICS', 2003, 72, 1, 2023, 72231, 4),
(48, 'SEC', 2791, 20, 1, 2407, 3524, 4),
(49, 'NAICS', 1026, 4243, 3, 1033, 424340, 5),
(50, 'NAICS', 1738, 56132, 4, 1737, 561320, 5),
(51, 'NAICS', 1943, 711, 2, 1961, 711320, 5),
(52, 'SIC', 4308, 20, 1, 3486, 3624, 4),
(53, 'NAICS', 1625, 541, 2, 1633, 541199, 5),
(54, 'NAICS', 2131, 814, 2, 2133, 814110, 5),
(55, 'SIC', 4075, 7380, 3, 4080, 7389, 4),
(56, 'SIC', 2982, 2000, 2, 3036, 2095, 4),
(57, 'SIC', 4311, 52, 1, 3905, 5962, 4),
(58, 'NAICS', 68, 1123, 3, 78, 11239, 4),
(59, 'SEC', 2794, 52, 1, 2620, 5500, 2),
(60, 'NAICS', 1402, 51, 1, 1472, 519110, 5),
(61, 'SIC', 4308, 20, 1, 3055, 2230, 3),
(62, 'NAICS', 2189, 9261, 3, 2192, 926120, 5),
(63, 'SIC', 3587, 3950, 3, 3588, 3951, 4),
(64, 'SIC', 4310, 50, 1, 3752, 5084, 4),
(65, 'SIC', 2798, 100, 2, 2821, 181, 4),
(66, 'SIC', 4311, 52, 1, 3832, 5451, 4),
(67, 'NAICS', 132, 21, 1, 177, 213113, 5),
(68, 'NAICS', 1725, 56, 1, 1772, 561621, 5),
(69, 'SIC', 3371, 3400, 2, 3410, 3491, 4),
(70, 'SIC', 4308, 20, 1, 3280, 3088, 4),
(71, 'SIC', 4308, 20, 1, 3182, 2672, 4),
(72, 'NAICS', 1979, 713, 2, 1999, 713950, 5),
(73, 'NAICS', 1850, 62, 1, 1939, 6244, 3),
(74, 'NAICS', 1733, 5613, 3, 1736, 561312, 5),
(75, 'NAICS', 182, 2211, 3, 188, 221115, 5),
(76, 'NAICS', 2135, 92, 1, 2194, 926130, 5),
(77, 'SIC', 3419, 3500, 2, 3468, 3580, 3),
(78, 'NAICS', 138, 212, 2, 170, 212393, 5),
(79, 'SIC', 2811, 160, 3, 2812, 161, 4),
(80, 'SIC', 4308, 20, 1, 3199, 2741, 4),
(81, 'NAICS', 1010, 42393, 4, 1009, 423930, 5),
(82, 'SEC', 2748, 7900, 2, 2752, 7997, 4),
(83, 'SIC', 4306, 10, 1, 2928, 1450, 3),
(84, 'SIC', 3050, 2200, 2, 3078, 2295, 4),
(85, 'NAICS', 930, 42, 1, 951, 423330, 5),
(86, 'NAICS', 2, 111, 2, 8, 111130, 5),
(87, 'SIC', 4308, 20, 1, 3243, 2874, 4),
(88, 'SIC', 2825, 200, 2, 2844, 279, 4),
(89, 'SEC', 2795, 60, 1, 2694, 6500, 2),
(90, 'SIC', 4305, 1, 1, 2834, 250, 3),
(91, 'SEC', 2791, 20, 1, 2326, 2835, 4),
(92, 'SIC', 4002, 6790, 3, 4005, 6798, 4),
(93, 'SIC', 4314, 90, 1, 4252, 9130, 3),
(94, 'NAICS', 1485, 522, 2, 1502, 522292, 5),
(95, 'NAICS', 138, 212, 2, 167, 21239, 4),
(96, 'SIC', 4312, 60, 1, 3968, 6360, 3),
(97, 'NAICS', 1979, 713, 2, 1996, 71393, 4),
(98, 'SIC', 3337, 3300, 2, 3358, 3354, 4),
(99, 'SIC', 3937, 6100, 2, 3938, 6110, 3),
(100, 'NAICS', 1985, 7132, 3, 1988, 713290, 5),
(101, 'NAICS', 1591, 532, 2, 1597, 53212, 4),
(102, 'NAICS', 56, 112, 2, 73, 112330, 5),
(103, 'SIC', 3083, 2300, 2, 3102, 2353, 4),
(104, 'SIC', 4268, 9400, 2, 4274, 9441, 4),
(105, 'NAICS', 931, 423, 2, 1008, 42392, 4),
(106, 'SIC', 4308, 20, 1, 3025, 2079, 4),
(107, 'SIC', 3570, 3850, 3, 3571, 3851, 4),
(108, 'NAICS', 1813, 611, 2, 1825, 61141, 4),
(109, 'SEC', 2689, 6390, 3, 2690, 6399, 4),
(110, 'NAICS', 1943, 711, 2, 1964, 711410, 5),
(111, 'SIC', 3496, 3640, 3, 3503, 3648, 4),
(112, 'SIC', 4308, 20, 1, 3431, 3535, 4),
(113, 'SIC', 4309, 40, 1, 3705, 4940, 3),
(114, 'SIC', 4308, 20, 1, 3240, 2869, 4),
(115, 'SIC', 3480, 3600, 2, 3514, 3674, 4),
(116, 'SIC', 4101, 7620, 3, 4103, 7623, 4),
(117, 'NAICS', 236, 2381, 3, 237, 238110, 5),
(118, 'NAICS', 930, 42, 1, 1010, 42393, 4),
(119, 'NAICS', 1569, 53, 1, 1622, 533110, 5),
(120, 'SIC', 4055, 7340, 3, 4057, 7349, 4),
(121, 'NAICS', 205, 23, 1, 245, 238150, 5),
(122, 'SEC', 2384, 3400, 2, 2385, 3410, 3),
(123, 'SEC', 2526, 4500, 2, 2527, 4510, 3),
(124, 'NAICS', 2, 111, 2, 30, 111332, 5),
(125, 'SIC', 3527, 3710, 3, 3531, 3715, 4),
(126, 'SIC', 3526, 3700, 2, 3544, 3760, 3),
(127, 'SIC', 4018, 7210, 3, 4019, 7211, 4),
(128, 'SEC', 2791, 20, 1, 2361, 3231, 4),
(129, 'SIC', 4040, 7300, 2, 4080, 7389, 4),
(130, 'NAICS', 931, 423, 2, 961, 42343, 4),
(131, 'SIC', 3769, 5130, 3, 3773, 5139, 4),
(132, 'NAICS', 1060, 42459, 4, 1059, 424590, 5),
(133, 'SIC', 2847, 700, 2, 2851, 721, 4),
(134, 'NAICS', 2071, 812, 2, 2102, 81299, 4),
(135, 'NAICS', 931, 423, 2, 978, 423620, 5),
(136, 'NAICS', 1969, 712, 2, 1976, 71213, 4),
(137, 'NAICS', 2021, 7223, 3, 2027, 72233, 4),
(138, 'NAICS', 2080, 8122, 3, 2084, 81222, 4),
(139, 'SIC', 4208, 8600, 2, 4211, 8620, 3),
(140, 'SEC', 2385, 3410, 3, 2387, 3412, 4),
(141, 'SIC', 4309, 40, 1, 3714, 4971, 4),
(142, 'NAICS', 1, 11, 1, 124, 115115, 5),
(143, 'SEC', 2384, 3400, 2, 2402, 3490, 3),
(144, 'SEC', 2796, 70, 1, 2718, 7331, 4),
(145, 'SIC', 3384, 3440, 3, 3390, 3448, 4),
(146, 'NAICS', 2103, 813, 2, 2110, 813212, 5),
(147, 'NAICS', 1920, 624, 2, 1926, 624190, 5),
(148, 'NAICS', 930, 42, 1, 1035, 4244, 3),
(149, 'SIC', 4307, 15, 1, 2981, 1799, 4),
(150, 'NAICS', 1726, 561, 2, 1742, 561410, 5),
(151, 'SIC', 3261, 3000, 2, 3279, 3087, 4),
(152, 'SEC', 2280, 2450, 3, 2282, 2452, 4),
(153, 'SEC', 2738, 7800, 2, 2741, 7819, 4),
(154, 'SIC', 3667, 4700, 2, 3675, 4741, 4),
(155, 'SIC', 4308, 20, 1, 3165, 2591, 4),
(156, 'NAICS', 2037, 81, 1, 2048, 81119, 4),
(157, 'NAICS', 1725, 56, 1, 1739, 561330, 5),
(158, 'SIC', 3384, 3440, 3, 3386, 3442, 4),
(159, 'SIC', 3992, 6700, 2, 4005, 6798, 4),
(160, 'NAICS', 930, 42, 1, 945, 42322, 4),
(161, 'SIC', 3715, 5000, 2, 3718, 5013, 4),
(162, 'NAICS', 1717, 54199, 4, 1716, 541990, 5),
(163, 'SEC', 2337, 2900, 2, 2341, 2990, 3),
(164, 'SIC', 4306, 10, 1, 2894, 1060, 3),
(165, 'NAICS', 931, 423, 2, 998, 423840, 5),
(166, 'NAICS', 1, 11, 1, 111, 114111, 5),
(167, 'NAICS', 2, 111, 2, 29, 111331, 5),
(168, 'SIC', 3721, 5020, 3, 3722, 5021, 4),
(169, 'NAICS', 1774, 5617, 3, 1780, 56173, 4),
(170, 'SIC', 3059, 2250, 3, 3062, 2253, 4),
(171, 'NAICS', 2150, 922, 2, 2156, 922130, 5),
(172, 'NAICS', 1513, 523, 2, 1527, 523910, 5),
(173, 'SIC', 3837, 5500, 2, 3847, 5551, 4),
(174, 'NAICS', 156, 2123, 3, 167, 21239, 4),
(175, 'SIC', 3854, 5600, 2, 3866, 5661, 4),
(176, 'SIC', 4302, 9900, 2, 4303, 9990, 3),
(177, 'NAICS', 1962, 71132, 4, 1961, 711320, 5),
(178, 'NAICS', 2058, 8113, 3, 2060, 81131, 4),
(179, 'SIC', 4308, 20, 1, 3417, 3498, 4),
(180, 'SIC', 4309, 40, 1, 3688, 4833, 4),
(181, 'SIC', 4307, 15, 1, 2975, 1790, 3),
(182, 'NAICS', 1419, 512, 2, 1428, 51219, 4),
(183, 'SIC', 2971, 1770, 3, 2972, 1771, 4),
(184, 'SIC', 3301, 3200, 2, 3309, 3240, 3),
(185, 'NAICS', 1726, 561, 2, 1768, 561611, 5),
(186, 'SIC', 3877, 5730, 3, 3878, 5731, 4),
(187, 'SEC', 2713, 7300, 2, 2730, 7377, 4),
(188, 'SIC', 3190, 2700, 2, 3213, 2796, 4),
(189, 'SIC', 4126, 7910, 3, 4127, 7911, 4),
(190, 'NAICS', 156, 2123, 3, 170, 212393, 5),
(191, 'NAICS', 930, 42, 1, 1012, 42394, 4),
(192, 'NAICS', 132, 21, 1, 153, 21229, 4),
(193, 'SIC', 3526, 3700, 2, 3531, 3715, 4),
(194, 'SEC', 2791, 20, 1, 2329, 2842, 4),
(195, 'NAICS', 1570, 531, 2, 1572, 531110, 5),
(196, 'SIC', 4313, 70, 1, 4164, 8063, 4),
(197, 'NAICS', 219, 2371, 3, 221, 23711, 4),
(198, 'NAICS', 1547, 5242, 3, 1549, 52421, 4),
(199, 'NAICS', 1, 11, 1, 92, 112920, 5),
(200, 'NAICS', 2071, 812, 2, 2094, 812910, 5),
(201, 'NAICS', 930, 42, 1, 1039, 42442, 4),
(202, 'NAICS', 1624, 54, 1, 1689, 5418, 3),
(203, 'NAICS', 1859, 6213, 3, 1870, 621399, 5),
(204, 'SIC', 2884, 1000, 2, 2892, 1041, 4),
(205, 'SIC', 4308, 20, 1, 3440, 3546, 4),
(206, 'SIC', 2798, 100, 2, 2824, 191, 4),
(207, 'NAICS', 1943, 711, 2, 1958, 7113, 3),
(208, 'SIC', 4146, 8000, 2, 4157, 8049, 4),
(209, 'NAICS', 98, 113, 2, 105, 1133, 3),
(210, 'NAICS', 1, 11, 1, 44, 111910, 5),
(211, 'NAICS', 1859, 6213, 3, 1868, 62139, 4),
(212, 'SEC', 2664, 6150, 3, 2665, 6153, 4),
(213, 'SEC', 2791, 20, 1, 2497, 3861, 4),
(214, 'NAICS', 1526, 5239, 3, 1534, 523991, 5),
(215, 'NAICS', 930, 42, 1, 971, 423510, 5),
(216, 'NAICS', 1624, 54, 1, 1661, 54142, 4),
(217, 'NAICS', 56, 112, 2, 96, 112990, 5),
(218, 'SIC', 3815, 5300, 2, 3819, 5331, 4),
(219, 'SIC', 3294, 3160, 3, 3295, 3161, 4),
(220, 'NAICS', 1980, 7131, 3, 1984, 71312, 4),
(221, 'NAICS', 138, 212, 2, 152, 212234, 5),
(222, 'NAICS', 1016, 4241, 3, 1017, 424110, 5),
(223, 'SIC', 4153, 8040, 3, 4156, 8043, 4),
(224, 'SIC', 4308, 20, 1, 3377, 3423, 4),
(225, 'SIC', 3886, 5900, 2, 3915, 5995, 4),
(226, 'SIC', 4312, 60, 1, 3939, 6111, 4),
(227, 'NAICS', 931, 423, 2, 992, 423810, 5),
(228, 'NAICS', 930, 42, 1, 975, 4236, 3),
(229, 'SIC', 4306, 10, 1, 2886, 1011, 4),
(230, 'NAICS', 946, 4233, 3, 950, 42332, 4),
(231, 'SIC', 3774, 5140, 3, 3780, 5146, 4),
(232, 'SIC', 3167, 2600, 2, 3187, 2677, 4),
(233, 'SIC', 3620, 4200, 2, 3625, 4215, 4),
(234, 'SIC', 2955, 1700, 2, 2976, 1791, 4),
(235, 'SEC', 2796, 70, 1, 2758, 8060, 3),
(236, 'NAICS', 1467, 5182, 3, 1468, 518210, 5),
(237, 'NAICS', 2010, 72119, 4, 2012, 721199, 5),
(238, 'SIC', 3552, 3800, 2, 3561, 3826, 4),
(239, 'SIC', 3636, 4400, 2, 3637, 4410, 3),
(240, 'SIC', 3886, 5900, 2, 3906, 5963, 4),
(241, 'NAICS', 1851, 621, 2, 1884, 621512, 5),
(242, 'NAICS', 1, 11, 1, 115, 114210, 5),
(243, 'NAICS', 2135, 92, 1, 2175, 92314, 4),
(244, 'NAICS', 153, 21229, 4, 155, 212299, 5),
(245, 'SIC', 4313, 70, 1, 4021, 7213, 4),
(246, 'SIC', 3214, 2800, 2, 3226, 2833, 4),
(247, 'NAICS', 2137, 9211, 3, 2148, 921190, 5),
(248, 'SEC', 2794, 52, 1, 2625, 5621, 4),
(249, 'NAICS', 1624, 54, 1, 1664, 541490, 5),
(250, 'NAICS', 132, 21, 1, 137, 211112, 5),
(251, 'SIC', 4308, 20, 1, 3317, 3261, 4),
(252, 'NAICS', 1506, 5223, 3, 1512, 52239, 4),
(253, 'NAICS', 1871, 6214, 3, 1874, 621420, 5),
(254, 'SIC', 3067, 2260, 3, 3069, 2262, 4),
(255, 'SIC', 3917, 6000, 2, 3931, 6080, 3),
(256, 'NAICS', 2182, 925, 2, 2186, 925120, 5),
(257, 'SIC', 3576, 3900, 2, 3593, 3961, 4),
(258, 'SIC', 4308, 20, 1, 3137, 2440, 3),
(259, 'NAICS', 1625, 541, 2, 1680, 54162, 4),
(260, 'SIC', 4309, 40, 1, 3622, 4212, 4),
(261, 'NAICS', 1792, 562, 2, 1798, 5622, 3),
(262, 'NAICS', 236, 2381, 3, 246, 23815, 4),
(263, 'SEC', 2224, 1380, 3, 2225, 1381, 4),
(264, 'NAICS', 1, 11, 1, 114, 1142, 3),
(265, 'SIC', 4308, 20, 1, 3327, 3275, 4),
(266, 'SIC', 3371, 3400, 2, 3404, 3480, 3),
(267, 'SIC', 4311, 52, 1, 3866, 5661, 4),
(268, 'NAICS', 1625, 541, 2, 1659, 54141, 4),
(269, 'SIC', 4208, 8600, 2, 4215, 8640, 3),
(270, 'NAICS', 1569, 53, 1, 1599, 532210, 5),
(271, 'NAICS', 1726, 561, 2, 1736, 561312, 5),
(272, 'SIC', 4268, 9400, 2, 4269, 9410, 3),
(273, 'NAICS', 1071, 4248, 3, 1075, 42482, 4),
(274, 'SIC', 3309, 3240, 3, 3310, 3241, 4),
(275, 'SIC', 4308, 20, 1, 3288, 3142, 4),
(276, 'SIC', 4312, 60, 1, 3918, 6010, 3),
(277, 'NAICS', 1, 11, 1, 9, 11113, 4),
(278, 'NAICS', 1740, 56133, 4, 1739, 561330, 5),
(279, 'SEC', 2795, 60, 1, 2699, 6530, 3),
(280, 'SIC', 3762, 5100, 2, 3788, 5160, 3),
(281, 'NAICS', 930, 42, 1, 989, 423740, 5),
(282, 'NAICS', 1420, 5121, 3, 1430, 512199, 5),
(283, 'SEC', 2229, 1500, 2, 2231, 1530, 3),
(284, 'SIC', 2882, 970, 3, 2883, 971, 4),
(285, 'SIC', 3301, 3200, 2, 3336, 3299, 4),
(286, 'SIC', 3605, 4100, 2, 3606, 4110, 3),
(287, 'SEC', 2588, 5090, 3, 2589, 5094, 4),
(288, 'NAICS', 167, 21239, 4, 168, 212391, 5),
(289, 'NAICS', 930, 42, 1, 1004, 4239, 3),
(290, 'SIC', 4305, 1, 1, 2806, 131, 4),
(291, 'SIC', 2858, 750, 3, 2860, 752, 4),
(292, 'NAICS', 205, 23, 1, 229, 2373, 3),
(293, 'SIC', 3468, 3580, 3, 3472, 3586, 4),
(294, 'NAICS', 931, 423, 2, 1013, 423990, 5),
(295, 'SEC', 2434, 3600, 2, 2444, 3651, 4),
(296, 'SIC', 4308, 20, 1, 3184, 2674, 4),
(297, 'SIC', 3083, 2300, 2, 3105, 2369, 4),
(298, 'SIC', 3925, 6030, 3, 3926, 6035, 4),
(299, 'SIC', 3000, 2040, 3, 3002, 2043, 4),
(300, 'SIC', 3371, 3400, 2, 3379, 3429, 4),
(301, 'SEC', 2791, 20, 1, 2390, 3433, 4),
(302, 'SIC', 3886, 5900, 2, 3911, 5990, 3),
(303, 'SIC', 4313, 70, 1, 4122, 7833, 4),
(304, 'SEC', 2795, 60, 1, 2658, 6099, 4),
(305, 'NAICS', 1850, 62, 1, 1891, 62199, 4),
(306, 'SIC', 4308, 20, 1, 3131, 2430, 3),
(307, 'NAICS', 1859, 6213, 3, 1861, 62131, 4),
(308, 'SIC', 3564, 3840, 3, 3565, 3841, 4),
(309, 'SIC', 4055, 7340, 3, 4056, 7342, 4),
(310, 'NAICS', 205, 23, 1, 235, 238, 2),
(311, 'NAICS', 1640, 5413, 3, 1646, 54133, 4),
(312, 'NAICS', 1554, 525, 2, 1568, 52599, 4),
(313, 'SEC', 2791, 20, 1, 2421, 3564, 4),
(314, 'NAICS', 1402, 51, 1, 1411, 511140, 5),
(315, 'SEC', 2683, 6330, 3, 2684, 6331, 4),
(316, 'SIC', 4305, 1, 1, 2801, 112, 4),
(317, 'NAICS', 1813, 611, 2, 1822, 61131, 4),
(318, 'SEC', 2753, 8000, 2, 2762, 8080, 3),
(319, 'NAICS', 2037, 81, 1, 2086, 812310, 5),
(320, 'NAICS', 2003, 72, 1, 2012, 721199, 5),
(321, 'SIC', 4308, 20, 1, 3248, 2892, 4),
(322, 'SIC', 3419, 3500, 2, 3476, 3593, 4),
(323, 'NAICS', 1725, 56, 1, 1804, 5629, 3),
(324, 'SEC', 2791, 20, 1, 2300, 2670, 3),
(325, 'NAICS', 1500, 52229, 4, 1501, 522291, 5),
(326, 'NAICS', 1850, 62, 1, 1883, 621511, 5),
(327, 'SIC', 4308, 20, 1, 3101, 2350, 3),
(328, 'SIC', 4313, 70, 1, 4243, 8811, 4),
(329, 'SIC', 2939, 1500, 2, 2947, 1542, 4),
(330, 'SIC', 3992, 6700, 2, 3993, 6710, 3),
(331, 'NAICS', 1452, 517, 2, 1459, 5174, 3),
(332, 'NAICS', 1015, 424, 2, 1072, 424810, 5),
(333, 'NAICS', 1549, 52421, 4, 1548, 524210, 5),
(334, 'NAICS', 1624, 54, 1, 1645, 541330, 5),
(335, 'SEC', 2539, 4800, 2, 2541, 4812, 4),
(336, 'NAICS', 2151, 9221, 3, 2163, 92216, 4),
(337, 'SIC', 3215, 2810, 3, 3217, 2813, 4),
(338, 'NAICS', 1657, 5414, 3, 1658, 541410, 5),
(339, 'NAICS', 1726, 561, 2, 1759, 561510, 5),
(340, 'NAICS', 205, 23, 1, 208, 23611, 4),
(341, 'NAICS', 1089, 425, 2, 1094, 42512, 4),
(342, 'NAICS', 1920, 624, 2, 1936, 6243, 3),
(343, 'NAICS', 2103, 813, 2, 2123, 813920, 5),
(344, 'SIC', 2825, 200, 2, 2840, 270, 3),
(345, 'SEC', 2796, 70, 1, 2744, 7829, 4),
(346, 'SIC', 3419, 3500, 2, 3425, 3524, 4),
(347, 'SEC', 2790, 15, 1, 2230, 1520, 3),
(348, 'SIC', 3012, 2060, 3, 3013, 2061, 4),
(349, 'NAICS', 1065, 42469, 4, 1064, 424690, 5),
(350, 'NAICS', 1804, 5629, 3, 1808, 56292, 4),
(351, 'SIC', 4313, 70, 1, 4044, 7313, 4),
(352, 'NAICS', 2020, 722, 2, 2030, 72241, 4),
(353, 'SIC', 4305, 1, 1, 2882, 970, 3),
(354, 'SIC', 3419, 3500, 2, 3449, 3556, 4),
(355, 'NAICS', 3, 1111, 3, 5, 11111, 4),
(356, 'SIC', 3083, 2300, 2, 3113, 2387, 4),
(357, 'SIC', 3667, 4700, 2, 3670, 4725, 4),
(358, 'NAICS', 218, 237, 2, 228, 23721, 4),
(359, 'NAICS', 1470, 519, 2, 1479, 51919, 4),
(360, 'SIC', 4313, 70, 1, 4231, 8731, 4),
(361, 'NAICS', 2113, 81331, 4, 2115, 813312, 5),
(362, 'SIC', 3762, 5100, 2, 3767, 5120, 3),
(363, 'NAICS', 1725, 56, 1, 1747, 56143, 4),
(364, 'NAICS', 930, 42, 1, 932, 4231, 3),
(365, 'SEC', 2371, 3300, 2, 2379, 3341, 4),
(366, 'NAICS', 273, 2389, 3, 274, 238910, 5),
(367, 'NAICS', 1998, 71394, 4, 1997, 713940, 5),
(368, 'NAICS', 1990, 7139, 3, 1993, 713920, 5),
(369, 'SEC', 2677, 6300, 2, 2682, 6324, 4),
(370, 'NAICS', 102, 1132, 3, 104, 11321, 4),
(371, 'NAICS', 931, 423, 2, 964, 423450, 5),
(372, 'NAICS', 1015, 424, 2, 1030, 42432, 4),
(373, 'NAICS', 180, 22, 1, 199, 221310, 5),
(374, 'SIC', 3891, 5930, 3, 3892, 5932, 4),
(375, 'NAICS', 930, 42, 1, 1032, 42433, 4),
(376, 'NAICS', 1471, 5191, 3, 1478, 519190, 5),
(377, 'NAICS', 982, 4237, 3, 984, 42371, 4),
(378, 'SIC', 3131, 2430, 3, 3132, 2431, 4),
(379, 'SIC', 3489, 3630, 3, 3493, 3634, 4),
(380, 'SIC', 4312, 60, 1, 3994, 6712, 4),
(381, 'SIC', 4313, 70, 1, 4025, 7218, 4),
(382, 'SIC', 3020, 2070, 3, 3023, 2076, 4),
(383, 'SIC', 4040, 7300, 2, 4078, 7383, 4),
(384, 'NAICS', 1076, 4249, 3, 1086, 42495, 4),
(385, 'NAICS', 2108, 81321, 4, 2109, 813211, 5),
(386, 'SIC', 4307, 15, 1, 2974, 1781, 4),
(387, 'SIC', 3050, 2200, 2, 3070, 2269, 4),
(388, 'SIC', 4311, 52, 1, 3876, 5722, 4),
(389, 'SIC', 4309, 40, 1, 3614, 4141, 4),
(390, 'SIC', 4308, 20, 1, 3098, 2340, 3),
(391, 'SIC', 3893, 5940, 3, 3897, 5944, 4),
(392, 'SIC', 2909, 1300, 2, 2913, 1321, 4),
(393, 'NAICS', 1611, 53231, 4, 1610, 532310, 5),
(394, 'NAICS', 2, 111, 2, 53, 111991, 5),
(395, 'SIC', 3048, 2140, 3, 3049, 2141, 4),
(396, 'NAICS', 1812, 61, 1, 1840, 61162, 4),
(397, 'SEC', 2789, 10, 1, 2225, 1381, 4),
(398, 'NAICS', 62, 11212, 4, 61, 112120, 5),
(399, 'SEC', 2791, 20, 1, 2444, 3651, 4),
(400, 'SIC', 4308, 20, 1, 3332, 3292, 4),
(401, 'SIC', 3693, 4900, 2, 3708, 4952, 4),
(402, 'SIC', 3886, 5900, 2, 3903, 5960, 3),
(403, 'SEC', 2355, 3200, 2, 2370, 3290, 3),
(404, 'SIC', 4308, 20, 1, 3181, 2671, 4),
(405, 'SIC', 3083, 2300, 2, 3119, 2394, 4),
(406, 'SEC', 2791, 20, 1, 2499, 3873, 4),
(407, 'NAICS', 1402, 51, 1, 1441, 51229, 4),
(408, 'SIC', 4308, 20, 1, 3306, 3229, 4),
(409, 'SEC', 2262, 2200, 2, 2267, 2250, 3),
(410, 'SEC', 2793, 50, 1, 2603, 5180, 3),
(411, 'SIC', 3576, 3900, 2, 3579, 3914, 4),
(412, 'NAICS', 932, 4231, 3, 935, 423120, 5),
(413, 'NAICS', 1725, 56, 1, 1746, 561422, 5),
(414, 'NAICS', 1452, 517, 2, 1461, 51741, 4),
(415, 'SIC', 4308, 20, 1, 2982, 2000, 2),
(416, 'SIC', 3555, 3820, 3, 3563, 3829, 4),
(417, 'SIC', 3461, 3570, 3, 3463, 3572, 4),
(418, 'SEC', 2795, 60, 1, 2702, 6552, 4),
(419, 'NAICS', 2080, 8122, 3, 2082, 81221, 4),
(420, 'SEC', 2794, 52, 1, 2627, 5651, 4),
(421, 'SIC', 4312, 60, 1, 3952, 6221, 4),
(422, 'SIC', 4313, 70, 1, 4229, 8721, 4),
(423, 'SIC', 3180, 2670, 3, 3189, 2679, 4),
(424, 'SIC', 4040, 7300, 2, 4051, 7334, 4),
(425, 'SIC', 3634, 4310, 3, 3635, 4311, 4),
(426, 'SIC', 4308, 20, 1, 3444, 3550, 3),
(427, 'SIC', 4313, 70, 1, 4023, 7216, 4),
(428, 'NAICS', 1, 11, 1, 49, 11193, 4),
(429, 'SEC', 2791, 20, 1, 2261, 2111, 4),
(430, 'NAICS', 1876, 62149, 4, 1879, 621493, 5),
(431, 'SIC', 3854, 5600, 2, 3857, 5620, 3),
(432, 'SEC', 2659, 6100, 2, 4320, 6170, 3),
(433, 'NAICS', 1084, 42494, 4, 1083, 424940, 5),
(434, 'SIC', 3167, 2600, 2, 3175, 2652, 4),
(435, 'NAICS', 205, 23, 1, 269, 238350, 5),
(436, 'SIC', 2948, 1600, 2, 2954, 1629, 4),
(437, 'NAICS', 1471, 5191, 3, 1477, 51913, 4),
(438, 'NAICS', 1871, 6214, 3, 1877, 621491, 5),
(439, 'NAICS', 1836, 6116, 3, 1839, 611620, 5),
(440, 'NAICS', 1851, 621, 2, 1886, 621610, 5),
(441, 'SIC', 4247, 9100, 2, 4249, 9111, 4),
(442, 'SIC', 3511, 3670, 3, 3513, 3672, 4),
(443, 'SIC', 4308, 20, 1, 3488, 3629, 4),
(444, 'NAICS', 1035, 4244, 3, 1053, 42449, 4),
(445, 'NAICS', 1624, 54, 1, 1683, 5417, 3),
(446, 'SIC', 4312, 60, 1, 3978, 6510, 3),
(447, 'SIC', 2955, 1700, 2, 2957, 1711, 4),
(448, 'SEC', 2794, 52, 1, 2646, 5960, 3),
(449, 'SEC', 2791, 20, 1, 2247, 2030, 3),
(450, 'NAICS', 117, 115, 2, 125, 115116, 5),
(451, 'SIC', 3301, 3200, 2, 3302, 3210, 3),
(452, 'SIC', 4308, 20, 1, 3129, 2426, 4),
(453, 'SIC', 3419, 3500, 2, 3462, 3571, 4),
(454, 'SIC', 3804, 5200, 2, 3812, 5261, 4),
(455, 'NAICS', 1624, 54, 1, 1634, 5412, 3),
(456, 'NAICS', 1, 11, 1, 58, 11211, 4),
(457, 'SIC', 4314, 90, 1, 4255, 9191, 4),
(458, 'SIC', 4082, 7510, 3, 4083, 7513, 4),
(459, 'SEC', 2791, 20, 1, 2397, 3451, 4),
(460, 'NAICS', 1741, 5614, 3, 1750, 561440, 5),
(461, 'SEC', 2403, 3500, 2, 2409, 3531, 4),
(462, 'NAICS', 56, 112, 2, 85, 11251, 4),
(463, 'NAICS', 930, 42, 1, 940, 42314, 4),
(464, 'NAICS', 1547, 5242, 3, 1553, 524298, 5),
(465, 'NAICS', 2093, 8129, 3, 2098, 812922, 5),
(466, 'SIC', 2798, 100, 2, 2804, 119, 4),
(467, 'SIC', 2909, 1300, 2, 2911, 1311, 4),
(468, 'NAICS', 2137, 9211, 3, 2147, 92115, 4),
(469, 'SEC', 2657, 6090, 3, 2658, 6099, 4),
(470, 'SIC', 4308, 20, 1, 3313, 3253, 4),
(471, 'SIC', 4310, 50, 1, 3716, 5010, 3),
(472, 'SIC', 3055, 2230, 3, 3056, 2231, 4),
(473, 'SIC', 4309, 40, 1, 3639, 4420, 3),
(474, 'SIC', 3083, 2300, 2, 3114, 2389, 4),
(475, 'NAICS', 138, 212, 2, 140, 21211, 4),
(476, 'NAICS', 1066, 4247, 3, 1069, 424720, 5),
(477, 'SEC', 2791, 20, 1, 2265, 2220, 3),
(478, 'SIC', 3993, 6710, 3, 3995, 6719, 4),
(479, 'NAICS', 1850, 62, 1, 1859, 6213, 3),
(480, 'SIC', 4269, 9410, 3, 4270, 9411, 4),
(481, 'NAICS', 1569, 53, 1, 1614, 532411, 5),
(482, 'NAICS', 1625, 541, 2, 1705, 54189, 4),
(483, 'SIC', 4228, 8720, 3, 4229, 8721, 4),
(484, 'SEC', 2791, 20, 1, 2476, 3800, 2),
(485, 'SEC', 2680, 6320, 3, 2681, 6321, 4),
(486, 'SIC', 2918, 1400, 2, 2920, 1411, 4),
(487, 'SIC', 3696, 4920, 3, 3700, 4925, 4),
(488, 'NAICS', 1871, 6214, 3, 1873, 62141, 4),
(489, 'SIC', 4308, 20, 1, 3268, 3053, 4),
(490, 'SIC', 4308, 20, 1, 3305, 3221, 4),
(491, 'SIC', 3083, 2300, 2, 3090, 2325, 4),
(492, 'SIC', 3167, 2600, 2, 3183, 2673, 4),
(493, 'NAICS', 1591, 532, 2, 1613, 53241, 4),
(494, 'SIC', 3693, 4900, 2, 3698, 4923, 4),
(495, 'NAICS', 1625, 541, 2, 1662, 541430, 5),
(496, 'NAICS', 2167, 9231, 3, 2172, 923130, 5),
(497, 'SIC', 3266, 3050, 3, 3267, 3052, 4),
(498, 'NAICS', 1443, 5151, 3, 1444, 51511, 4),
(499, 'NAICS', 1928, 6242, 3, 1933, 624229, 5),
(500, 'SIC', 3338, 3310, 3, 3343, 3317, 4),
(501, 'SEC', 2792, 40, 1, 2565, 4953, 4),
(502, 'NAICS', 2037, 81, 1, 2134, 81411, 4),
(503, 'NAICS', 1881, 6215, 3, 1883, 621511, 5),
(504, 'NAICS', 1402, 51, 1, 1418, 51121, 4),
(505, 'SEC', 2791, 20, 1, 2285, 2511, 4),
(506, 'SIC', 3384, 3440, 3, 3385, 3441, 4),
(507, 'NAICS', 1598, 5322, 3, 1599, 532210, 5),
(508, 'SIC', 4308, 20, 1, 3163, 2542, 4),
(509, 'SEC', 2649, 6000, 2, 2652, 6022, 4),
(510, 'SIC', 4100, 7600, 2, 4102, 7622, 4),
(511, 'NAICS', 182, 2211, 3, 185, 221112, 5),
(512, 'NAICS', 1591, 532, 2, 1606, 532291, 5),
(513, 'NAICS', 1943, 711, 2, 1967, 711510, 5),
(514, 'NAICS', 1526, 5239, 3, 1535, 523999, 5),
(515, 'SEC', 2568, 5000, 2, 2574, 5040, 3),
(516, 'SIC', 4314, 90, 1, 4287, 9620, 3),
(517, 'SIC', 4308, 20, 1, 3513, 3672, 4),
(518, 'NAICS', 2135, 92, 1, 2178, 924110, 5),
(519, 'SIC', 4311, 52, 1, 3857, 5620, 3),
(520, 'NAICS', 1554, 525, 2, 1558, 525120, 5),
(521, 'NAICS', 1, 11, 1, 94, 112930, 5),
(522, 'NAICS', 98, 113, 2, 103, 113210, 5),
(523, 'NAICS', 931, 423, 2, 985, 423720, 5),
(524, 'NAICS', 1969, 712, 2, 1972, 71211, 4),
(525, 'SIC', 3985, 6530, 3, 3986, 6531, 4),
(526, 'SIC', 4308, 20, 1, 3554, 3812, 4),
(527, 'SIC', 3077, 2290, 3, 3080, 2297, 4),
(528, 'NAICS', 1485, 522, 2, 1488, 52211, 4),
(529, 'NAICS', 1583, 5313, 3, 1590, 53139, 4),
(530, 'SIC', 4075, 7380, 3, 4078, 7383, 4),
(531, 'SIC', 3137, 2440, 3, 3139, 2448, 4),
(532, 'SIC', 4018, 7210, 3, 4020, 7212, 4),
(533, 'SIC', 3050, 2200, 2, 3079, 2296, 4),
(534, 'SIC', 4311, 52, 1, 3883, 5810, 3),
(535, 'SIC', 2982, 2000, 2, 3001, 2041, 4),
(536, 'SIC', 4309, 40, 1, 3689, 4840, 3),
(537, 'NAICS', 1536, 524, 2, 1538, 52411, 4),
(538, 'SIC', 3480, 3600, 2, 3504, 3650, 3),
(539, 'NAICS', 1852, 6211, 3, 1854, 621111, 5),
(540, 'SIC', 4309, 40, 1, 3658, 4520, 3),
(541, 'NAICS', 1979, 713, 2, 1981, 713110, 5),
(542, 'NAICS', 1812, 61, 1, 1817, 6112, 3),
(543, 'SIC', 4306, 10, 1, 2884, 1000, 2),
(544, 'NAICS', 1725, 56, 1, 1726, 561, 2),
(545, 'SIC', 3282, 3100, 2, 3287, 3140, 3),
(546, 'NAICS', 1640, 5413, 3, 1642, 54131, 4),
(547, 'NAICS', 205, 23, 1, 267, 238340, 5),
(548, 'NAICS', 930, 42, 1, 1038, 424420, 5),
(549, 'SIC', 4308, 20, 1, 3343, 3317, 4),
(550, 'NAICS', 2126, 81393, 4, 2125, 813930, 5),
(551, 'NAICS', 2038, 811, 2, 2048, 81119, 4),
(552, 'NAICS', 1741, 5614, 3, 1753, 56145, 4),
(553, 'NAICS', 1035, 4244, 3, 1040, 424430, 5),
(554, 'NAICS', 1809, 56299, 4, 1811, 562998, 5),
(555, 'NAICS', 1725, 56, 1, 1798, 5622, 3),
(556, 'NAICS', 1882, 62151, 4, 1883, 621511, 5),
(557, 'SEC', 2670, 6200, 2, 2676, 6282, 4),
(558, 'SIC', 3419, 3500, 2, 3460, 3569, 4),
(559, 'NAICS', 1453, 5171, 3, 1454, 517110, 5),
(560, 'SIC', 4308, 20, 1, 3263, 3011, 4),
(561, 'SIC', 3252, 2900, 2, 3258, 2990, 3),
(562, 'SIC', 3680, 4800, 2, 3691, 4890, 3),
(563, 'SIC', 4311, 52, 1, 3844, 5540, 3),
(564, 'NAICS', 1480, 52, 1, 1529, 523920, 5),
(565, 'SEC', 2774, 8700, 2, 2781, 8741, 4),
(566, 'SIC', 3059, 2250, 3, 3064, 2257, 4),
(567, 'NAICS', 2072, 8121, 3, 2075, 812112, 5),
(568, 'NAICS', 1699, 54185, 4, 1698, 541850, 5),
(569, 'NAICS', 1634, 5412, 3, 1637, 541213, 5),
(570, 'NAICS', 235, 238, 2, 251, 238190, 5),
(571, 'NAICS', 982, 4237, 3, 986, 42372, 4),
(572, 'NAICS', 1591, 532, 2, 1612, 5324, 3),
(573, 'SIC', 3330, 3290, 3, 3331, 3291, 4),
(574, 'NAICS', 1015, 424, 2, 1065, 42469, 4),
(575, 'NAICS', 2037, 81, 1, 2114, 813311, 5),
(576, 'SIC', 3654, 4500, 2, 3657, 4513, 4),
(577, 'SEC', 2302, 2700, 2, 2318, 2790, 3),
(578, 'NAICS', 1480, 52, 1, 1488, 52211, 4),
(579, 'SIC', 4310, 50, 1, 3725, 5031, 4),
(580, 'SEC', 2384, 3400, 2, 2389, 3430, 3),
(581, 'SEC', 2791, 20, 1, 2352, 3089, 4),
(582, 'SIC', 3869, 5700, 2, 3874, 5719, 4),
(583, 'SEC', 2240, 2000, 2, 2248, 2033, 4),
(584, 'NAICS', 1625, 541, 2, 1671, 541519, 5),
(585, 'SIC', 3886, 5900, 2, 3904, 5961, 4),
(586, 'NAICS', 1725, 56, 1, 1803, 562219, 5),
(587, 'SIC', 2884, 1000, 2, 2894, 1060, 3),
(588, 'SIC', 4313, 70, 1, 4016, 7041, 4),
(589, 'NAICS', 205, 23, 1, 274, 238910, 5),
(590, 'NAICS', 2108, 81321, 4, 2111, 813219, 5),
(591, 'NAICS', 2037, 81, 1, 2079, 812199, 5),
(592, 'NAICS', 28, 11133, 4, 31, 111333, 5),
(593, 'NAICS', 1734, 56131, 4, 1736, 561312, 5),
(594, 'SIC', 3489, 3630, 3, 3495, 3639, 4),
(595, 'NAICS', 1726, 561, 2, 1755, 561491, 5),
(596, 'NAICS', 2058, 8113, 3, 2059, 811310, 5),
(597, 'SIC', 4309, 40, 1, 3702, 4931, 4),
(598, 'SIC', 4081, 7500, 2, 4098, 7542, 4),
(599, 'NAICS', 1513, 523, 2, 1514, 5231, 3),
(600, 'SIC', 4309, 40, 1, 3672, 4730, 3),
(601, 'NAICS', 2038, 811, 2, 2068, 81143, 4),
(602, 'SEC', 2794, 52, 1, 2606, 5210, 3),
(603, 'SIC', 4313, 70, 1, 4242, 8810, 3),
(604, 'SEC', 4324, 6190, 3, 4325, 6199, 4),
(605, 'SIC', 4308, 20, 1, 3017, 2066, 4),
(606, 'SEC', 2793, 50, 1, 2587, 5084, 4),
(607, 'NAICS', 1725, 56, 1, 1750, 561440, 5),
(608, 'NAICS', 2038, 811, 2, 2058, 8113, 3),
(609, 'SIC', 4308, 20, 1, 3582, 3931, 4),
(610, 'SIC', 3355, 3350, 3, 3358, 3354, 4),
(611, 'SIC', 4308, 20, 1, 3418, 3499, 4),
(612, 'NAICS', 1850, 62, 1, 1885, 6216, 3),
(613, 'SIC', 4308, 20, 1, 3477, 3594, 4),
(614, 'NAICS', 975, 4236, 3, 979, 42362, 4),
(615, 'NAICS', 1015, 424, 2, 1026, 4243, 3),
(616, 'NAICS', 1726, 561, 2, 1764, 561591, 5),
(617, 'SIC', 4305, 1, 1, 2832, 240, 3),
(618, 'SIC', 4311, 52, 1, 3870, 5710, 3),
(619, 'NAICS', 132, 21, 1, 144, 2122, 3),
(620, 'NAICS', 1613, 53241, 4, 1615, 532412, 5),
(621, 'NAICS', 930, 42, 1, 1022, 42413, 4),
(622, 'SIC', 3964, 6330, 3, 3965, 6331, 4),
(623, 'SIC', 3715, 5000, 2, 3744, 5070, 3),
(624, 'SEC', 2791, 20, 1, 2269, 2270, 3),
(625, 'SIC', 4311, 52, 1, 3907, 5980, 3),
(626, 'NAICS', 1, 11, 1, 64, 11213, 4),
(627, 'SEC', 2791, 20, 1, 2431, 3580, 3),
(628, 'SIC', 3822, 5400, 2, 3828, 5431, 4),
(629, 'SIC', 3316, 3260, 3, 3318, 3262, 4),
(630, 'NAICS', 132, 21, 1, 147, 21222, 4),
(631, 'NAICS', 1513, 523, 2, 1515, 523110, 5),
(632, 'SIC', 3371, 3400, 2, 3372, 3410, 3),
(633, 'SEC', 2552, 4900, 2, 2559, 4930, 3),
(634, 'SIC', 4308, 20, 1, 3388, 3444, 4),
(635, 'SIC', 4306, 10, 1, 2923, 1423, 4),
(636, 'SIC', 4308, 20, 1, 3260, 2999, 4),
(637, 'NAICS', 1513, 523, 2, 1523, 5232, 3),
(638, 'SIC', 4306, 10, 1, 2892, 1041, 4),
(639, 'SEC', 2791, 20, 1, 2425, 3571, 4),
(640, 'SIC', 4289, 9630, 3, 4290, 9631, 4),
(641, 'NAICS', 198, 2213, 3, 203, 221330, 5),
(642, 'NAICS', 1462, 5179, 3, 1463, 51791, 4),
(643, 'SIC', 4313, 70, 1, 4027, 7220, 3),
(644, 'SIC', 3762, 5100, 2, 3793, 5172, 4),
(645, 'SIC', 3729, 5040, 3, 3735, 5048, 4),
(646, 'NAICS', 1850, 62, 1, 1896, 622110, 5),
(647, 'NAICS', 2013, 7212, 3, 2016, 721214, 5),
(648, 'NAICS', 931, 423, 2, 1003, 42386, 4),
(649, 'NAICS', 930, 42, 1, 1051, 42448, 4),
(650, 'NAICS', 1942, 71, 1, 1958, 7113, 3),
(651, 'NAICS', 2003, 72, 1, 2036, 722515, 5),
(652, 'SEC', 2796, 70, 1, 2775, 8710, 3),
(653, 'NAICS', 98, 113, 2, 107, 11331, 4),
(654, 'NAICS', 1561, 52519, 4, 1560, 525190, 5),
(655, 'NAICS', 1570, 531, 2, 1575, 53112, 4),
(656, 'NAICS', 1725, 56, 1, 1769, 561612, 5),
(657, 'SEC', 2518, 4210, 3, 2519, 4213, 4),
(658, 'SIC', 3301, 3200, 2, 3304, 3220, 3),
(659, 'SIC', 4203, 8400, 2, 4204, 8410, 3),
(660, 'NAICS', 1635, 54121, 4, 1637, 541213, 5),
(661, 'SIC', 4310, 50, 1, 3794, 5180, 3),
(662, 'NAICS', 1725, 56, 1, 1778, 56172, 4),
(663, 'NAICS', 1850, 62, 1, 1920, 624, 2),
(664, 'NAICS', 2038, 811, 2, 2050, 811192, 5),
(665, 'SIC', 4308, 20, 1, 3126, 2411, 4),
(666, 'SIC', 3451, 3560, 3, 3457, 3566, 4),
(667, 'NAICS', 2, 111, 2, 40, 11142, 4),
(668, 'NAICS', 1403, 511, 2, 1410, 51113, 4),
(669, 'SIC', 3241, 2870, 3, 3245, 2879, 4),
(670, 'SIC', 3564, 3840, 3, 3568, 3844, 4),
(671, 'SIC', 3552, 3800, 2, 3554, 3812, 4),
(672, 'NAICS', 1813, 611, 2, 1831, 61151, 4),
(673, 'NAICS', 132, 21, 1, 159, 212312, 5),
(674, 'NAICS', 2135, 92, 1, 2155, 92212, 4),
(675, 'SEC', 2791, 20, 1, 2377, 3334, 4),
(676, 'SIC', 3968, 6360, 3, 3969, 6361, 4),
(677, 'SEC', 2283, 2500, 2, 2285, 2511, 4),
(678, 'SIC', 3419, 3500, 2, 3436, 3542, 4),
(679, 'NAICS', 1, 11, 1, 11, 11114, 4),
(680, 'NAICS', 1510, 52232, 4, 1509, 522320, 5),
(681, 'NAICS', 1402, 51, 1, 1403, 511, 2),
(682, 'SEC', 2234, 1600, 2, 2235, 1620, 3),
(683, 'SIC', 3833, 5460, 3, 3834, 5461, 4),
(684, 'NAICS', 931, 423, 2, 1011, 423940, 5),
(685, 'NAICS', 931, 423, 2, 994, 423820, 5),
(686, 'NAICS', 1431, 5122, 3, 1436, 512230, 5),
(687, 'SIC', 3083, 2300, 2, 3095, 2335, 4),
(688, 'NAICS', 1979, 713, 2, 2002, 71399, 4),
(689, 'SEC', 2479, 3820, 3, 2486, 3827, 4),
(690, 'SIC', 4313, 70, 1, 4208, 8600, 2),
(691, 'SEC', 2792, 40, 1, 2518, 4210, 3),
(692, 'SIC', 4303, 9990, 3, 4304, 9999, 4),
(693, 'NAICS', 253, 2382, 3, 258, 238290, 5),
(694, 'SIC', 3434, 3540, 3, 3442, 3548, 4),
(695, 'NAICS', 173, 2131, 3, 175, 213111, 5),
(696, 'SEC', 2796, 70, 1, 2737, 7600, 2),
(697, 'SIC', 2884, 1000, 2, 2886, 1011, 4),
(698, 'NAICS', 182, 2211, 3, 184, 221111, 5),
(699, 'NAICS', 1831, 61151, 4, 1833, 611512, 5),
(700, 'SEC', 2749, 7940, 3, 2750, 7948, 4),
(701, 'SIC', 3423, 3520, 3, 3425, 3524, 4),
(702, 'SIC', 4305, 1, 1, 2831, 219, 4),
(703, 'SIC', 2918, 1400, 2, 2934, 1479, 4),
(704, 'SIC', 4311, 52, 1, 3909, 5984, 4),
(705, 'SIC', 3124, 2400, 2, 3147, 2499, 4),
(706, 'SIC', 4308, 20, 1, 3429, 3533, 4),
(707, 'SIC', 4312, 60, 1, 3946, 6162, 4),
(708, 'NAICS', 1813, 611, 2, 1838, 61161, 4),
(709, 'SIC', 3353, 3340, 3, 3354, 3341, 4),
(710, 'SIC', 4312, 60, 1, 3919, 6011, 4),
(711, 'SIC', 4313, 70, 1, 4192, 8300, 2),
(712, 'SEC', 2713, 7300, 2, 2720, 7350, 3),
(713, 'NAICS', 931, 423, 2, 1007, 423920, 5),
(714, 'NAICS', 1419, 512, 2, 1431, 5122, 3),
(715, 'NAICS', 156, 2123, 3, 162, 21232, 4),
(716, 'SEC', 2789, 10, 1, 2223, 1311, 4),
(717, 'NAICS', 1078, 42491, 4, 1077, 424910, 5),
(718, 'SIC', 4313, 70, 1, 4176, 8110, 3),
(719, 'SEC', 2791, 20, 1, 2346, 3021, 4),
(720, 'SIC', 2799, 110, 3, 2801, 112, 4),
(721, 'SIC', 3774, 5140, 3, 3779, 5145, 4),
(722, 'NAICS', 930, 42, 1, 941, 4232, 3),
(723, 'NAICS', 2003, 72, 1, 2008, 721120, 5),
(724, 'SIC', 3840, 5520, 3, 3841, 5521, 4),
(725, 'NAICS', 1970, 7121, 3, 1972, 71211, 4),
(726, 'NAICS', 1402, 51, 1, 1475, 51912, 4),
(727, 'NAICS', 1725, 56, 1, 1730, 5612, 3),
(728, 'SIC', 4308, 20, 1, 3093, 2330, 3),
(729, 'NAICS', 931, 423, 2, 966, 423460, 5),
(730, 'NAICS', 1920, 624, 2, 1923, 62411, 4),
(731, 'SIC', 4308, 20, 1, 3376, 3421, 4),
(732, 'SIC', 3999, 6730, 3, 4001, 6733, 4),
(733, 'NAICS', 85, 11251, 4, 86, 112511, 5),
(734, 'SEC', 2405, 3520, 3, 2407, 3524, 4),
(735, 'NAICS', 1942, 71, 1, 1966, 7115, 3),
(736, 'NAICS', 2135, 92, 1, 2162, 922160, 5),
(737, 'SEC', 2791, 20, 1, 2430, 3579, 4),
(738, 'SIC', 3875, 5720, 3, 3876, 5722, 4),
(739, 'NAICS', 1667, 54151, 4, 1671, 541519, 5),
(740, 'SEC', 2789, 10, 1, 2221, 1300, 2),
(741, 'NAICS', 930, 42, 1, 1085, 424950, 5),
(742, 'SIC', 3715, 5000, 2, 3752, 5084, 4),
(743, 'SEC', 2345, 3020, 3, 2346, 3021, 4),
(744, 'NAICS', 2003, 72, 1, 2014, 72121, 4),
(745, 'SEC', 2450, 3670, 3, 2452, 3674, 4),
(746, 'SEC', 2796, 70, 1, 2769, 8200, 2),
(747, 'SEC', 2791, 20, 1, 2494, 3850, 3),
(748, 'SEC', 2792, 40, 1, 2523, 4400, 2),
(749, 'NAICS', 1725, 56, 1, 1738, 56132, 4),
(750, 'SIC', 3371, 3400, 2, 3412, 3493, 4),
(751, 'SIC', 4284, 9600, 2, 4293, 9650, 3),
(752, 'SIC', 4125, 7900, 2, 4129, 7922, 4),
(753, 'SIC', 3451, 3560, 3, 3459, 3568, 4),
(754, 'SIC', 2798, 100, 2, 2811, 160, 3),
(755, 'SEC', 2221, 1300, 2, 2225, 1381, 4),
(756, 'SIC', 4277, 9500, 2, 4280, 9512, 4),
(757, 'SEC', 2739, 7810, 3, 2740, 7812, 4),
(758, 'NAICS', 43, 1119, 3, 44, 111910, 5),
(759, 'NAICS', 1914, 62331, 4, 1916, 623312, 5),
(760, 'SIC', 3480, 3600, 2, 3502, 3647, 4),
(761, 'SIC', 3855, 5610, 3, 3856, 5611, 4),
(762, 'SIC', 4040, 7300, 2, 4053, 7336, 4),
(763, 'SIC', 2847, 700, 2, 2850, 720, 3),
(764, 'SIC', 3000, 2040, 3, 3007, 2048, 4),
(765, 'SIC', 4309, 40, 1, 3657, 4513, 4),
(766, 'NAICS', 1683, 5417, 3, 1686, 541712, 5),
(767, 'SEC', 2458, 3700, 2, 2461, 3713, 4),
(768, 'SIC', 4309, 40, 1, 3607, 4111, 4),
(769, 'NAICS', 1591, 532, 2, 1601, 532220, 5),
(770, 'SIC', 4313, 70, 1, 4086, 7519, 4),
(771, 'NAICS', 2072, 8121, 3, 2074, 812111, 5),
(772, 'SIC', 3161, 2540, 3, 3163, 2542, 4),
(773, 'SIC', 3663, 4610, 3, 3664, 4612, 4),
(774, 'SEC', 2524, 4410, 3, 2525, 4412, 4),
(775, 'SEC', 2794, 52, 1, 2629, 5661, 4),
(776, 'SIC', 3214, 2800, 2, 3246, 2890, 3),
(777, 'SIC', 3837, 5500, 2, 3843, 5531, 4),
(778, 'SIC', 4277, 9500, 2, 4279, 9511, 4),
(779, 'SIC', 4313, 70, 1, 4173, 8093, 4),
(780, 'SIC', 4309, 40, 1, 3610, 4121, 4),
(781, 'NAICS', 1725, 56, 1, 1753, 56145, 4),
(782, 'SEC', 2791, 20, 1, 2309, 2732, 4),
(783, 'SEC', 2403, 3500, 2, 2431, 3580, 3),
(784, 'NAICS', 1942, 71, 1, 1963, 7114, 3),
(785, 'NAICS', 2183, 9251, 3, 2184, 925110, 5),
(786, 'SIC', 3384, 3440, 3, 3391, 3449, 4),
(787, 'NAICS', 139, 2121, 3, 141, 212111, 5),
(788, 'NAICS', 1850, 62, 1, 1854, 621111, 5),
(789, 'SIC', 3371, 3400, 2, 3407, 3484, 4),
(790, 'NAICS', 246, 23815, 4, 245, 238150, 5),
(791, 'NAICS', 119, 11511, 4, 120, 115111, 5),
(792, 'SIC', 4208, 8600, 2, 4220, 8661, 4),
(793, 'SIC', 3098, 2340, 3, 3099, 2341, 4),
(794, 'SIC', 3301, 3200, 2, 3330, 3290, 3),
(795, 'SIC', 3667, 4700, 2, 3668, 4720, 3),
(796, 'NAICS', 1452, 517, 2, 1463, 51791, 4),
(797, 'NAICS', 1, 11, 1, 21, 111211, 5),
(798, 'NAICS', 2037, 81, 1, 2132, 8141, 3),
(799, 'SIC', 3693, 4900, 2, 3706, 4941, 4),
(800, 'SIC', 3409, 3490, 3, 3417, 3498, 4),
(801, 'NAICS', 1850, 62, 1, 1933, 624229, 5),
(802, 'SIC', 4308, 20, 1, 3018, 2067, 4),
(803, 'NAICS', 1850, 62, 1, 1922, 624110, 5),
(804, 'NAICS', 1015, 424, 2, 1070, 42472, 4),
(805, 'NAICS', 1831, 61151, 4, 1835, 611519, 5),
(806, 'SIC', 3520, 3690, 3, 3522, 3692, 4),
(807, 'NAICS', 941, 4232, 3, 943, 42321, 4),
(808, 'SIC', 2798, 100, 2, 2801, 112, 4),
(809, 'NAICS', 1090, 4251, 3, 1091, 425110, 5),
(810, 'SEC', 2384, 3400, 2, 2396, 3450, 3),
(811, 'SIC', 4040, 7300, 2, 4064, 7363, 4),
(812, 'SIC', 4305, 1, 1, 2819, 179, 4),
(813, 'SIC', 3716, 5010, 3, 3717, 5012, 4),
(814, 'SIC', 4305, 1, 1, 2836, 252, 4),
(815, 'NAICS', 2165, 92219, 4, 2164, 922190, 5),
(816, 'SEC', 2791, 20, 1, 2371, 3300, 2),
(817, 'NAICS', 1536, 524, 2, 1552, 524292, 5),
(818, 'SEC', 2796, 70, 1, 2747, 7841, 4),
(819, 'NAICS', 930, 42, 1, 1049, 42447, 4),
(820, 'SIC', 4308, 20, 1, 3251, 2899, 4),
(821, 'SIC', 4313, 70, 1, 4163, 8062, 4),
(822, 'NAICS', 2, 111, 2, 19, 1112, 3),
(823, 'NAICS', 931, 423, 2, 969, 42349, 4),
(824, 'NAICS', 68, 1123, 3, 70, 11231, 4),
(825, 'SIC', 4308, 20, 1, 2999, 2038, 4),
(826, 'NAICS', 205, 23, 1, 254, 238210, 5),
(827, 'SEC', 2795, 60, 1, 2679, 6311, 4),
(828, 'SIC', 4310, 50, 1, 3784, 5150, 3),
(829, 'NAICS', 2191, 92611, 4, 2190, 926110, 5),
(830, 'SIC', 3301, 3200, 2, 3303, 3211, 4),
(831, 'SIC', 3762, 5100, 2, 3796, 5182, 4),
(832, 'SIC', 2847, 700, 2, 2860, 752, 4),
(833, 'SIC', 3167, 2600, 2, 3170, 2620, 3),
(834, 'SEC', 2391, 3440, 3, 2392, 3442, 4),
(835, 'SIC', 4308, 20, 1, 3112, 2386, 4),
(836, 'SIC', 4309, 40, 1, 3641, 4430, 3),
(837, 'SIC', 4308, 20, 1, 3525, 3699, 4),
(838, 'SIC', 3609, 4120, 3, 3610, 4121, 4),
(839, 'NAICS', 2, 111, 2, 10, 111140, 5),
(840, 'NAICS', 1823, 6114, 3, 1827, 61142, 4),
(841, 'NAICS', 1813, 611, 2, 1832, 611511, 5),
(842, 'SIC', 4308, 20, 1, 3110, 2384, 4),
(843, 'SIC', 4311, 52, 1, 3913, 5993, 4),
(844, 'NAICS', 1555, 5251, 3, 1559, 52512, 4),
(845, 'SIC', 3769, 5130, 3, 3771, 5136, 4),
(846, 'SIC', 4308, 20, 1, 3403, 3479, 4),
(847, 'NAICS', 930, 42, 1, 1069, 424720, 5),
(848, 'NAICS', 1792, 562, 2, 1807, 562920, 5),
(849, 'NAICS', 2137, 9211, 3, 2146, 921150, 5),
(850, 'SIC', 4203, 8400, 2, 4205, 8412, 4),
(851, 'NAICS', 1816, 61111, 4, 1815, 611110, 5),
(852, 'NAICS', 2112, 8133, 3, 2113, 81331, 4),
(853, 'SIC', 3012, 2060, 3, 3019, 2068, 4),
(854, 'SEC', 2785, 9700, 2, 2787, 9721, 4),
(855, 'NAICS', 2135, 92, 1, 2158, 922140, 5),
(856, 'SIC', 2982, 2000, 2, 3030, 2085, 4),
(857, 'SIC', 2982, 2000, 2, 3037, 2096, 4),
(858, 'SIC', 3693, 4900, 2, 3696, 4920, 3),
(859, 'NAICS', 1850, 62, 1, 1910, 62321, 4),
(860, 'NAICS', 2112, 8133, 3, 2115, 813312, 5),
(861, 'SEC', 2286, 2520, 3, 2287, 2522, 4),
(862, 'SIC', 4314, 90, 1, 4288, 9621, 4),
(863, 'SEC', 2791, 20, 1, 2320, 2810, 3),
(864, 'SEC', 2611, 5310, 3, 2612, 5311, 4),
(865, 'SIC', 4308, 20, 1, 3023, 2076, 4),
(866, 'NAICS', 205, 23, 1, 252, 23819, 4),
(867, 'NAICS', 109, 1141, 3, 110, 11411, 4),
(868, 'NAICS', 223, 23712, 4, 222, 237120, 5),
(869, 'NAICS', 930, 42, 1, 952, 42333, 4),
(870, 'SIC', 2798, 100, 2, 2806, 131, 4),
(871, 'NAICS', 2039, 8111, 3, 2043, 811113, 5),
(872, 'SIC', 3791, 5170, 3, 3792, 5171, 4),
(873, 'SEC', 2526, 4500, 2, 2533, 4581, 4),
(874, 'SEC', 2753, 8000, 2, 2757, 8051, 4),
(875, 'SEC', 2694, 6500, 2, 2701, 6550, 3),
(876, 'SIC', 3937, 6100, 2, 3939, 6111, 4),
(877, 'NAICS', 235, 238, 2, 241, 238130, 5),
(878, 'NAICS', 930, 42, 1, 977, 42361, 4),
(879, 'SIC', 3815, 5300, 2, 3821, 5399, 4),
(880, 'NAICS', 2103, 813, 2, 2109, 813211, 5),
(881, 'NAICS', 1463, 51791, 4, 1465, 517919, 5),
(882, 'NAICS', 16, 11119, 4, 17, 111191, 5),
(883, 'NAICS', 931, 423, 2, 976, 423610, 5),
(884, 'SIC', 3168, 2610, 3, 3169, 2611, 4),
(885, 'NAICS', 1812, 61, 1, 1814, 6111, 3),
(886, 'NAICS', 1625, 541, 2, 1685, 541711, 5),
(887, 'NAICS', 218, 237, 2, 225, 23713, 4),
(888, 'SIC', 4307, 15, 1, 2946, 1541, 4),
(889, 'SIC', 3426, 3530, 3, 3427, 3531, 4),
(890, 'SIC', 3180, 2670, 3, 3187, 2677, 4),
(891, 'SEC', 2791, 20, 1, 2317, 2780, 3),
(892, 'NAICS', 930, 42, 1, 1093, 425120, 5),
(893, 'NAICS', 2135, 92, 1, 2207, 92811, 4),
(894, 'NAICS', 2204, 928, 2, 2206, 928110, 5),
(895, 'NAICS', 85, 11251, 4, 87, 112512, 5),
(896, 'SIC', 2918, 1400, 2, 2930, 1459, 4),
(897, 'NAICS', 138, 212, 2, 162, 21232, 4),
(898, 'SIC', 3474, 3590, 3, 3476, 3593, 4),
(899, 'SIC', 3073, 2280, 3, 3076, 2284, 4),
(900, 'SIC', 3526, 3700, 2, 3547, 3769, 4),
(901, 'SIC', 4308, 20, 1, 3411, 3492, 4),
(902, 'NAICS', 1420, 5121, 3, 1425, 51213, 4),
(903, 'SIC', 4306, 10, 1, 2904, 1222, 4),
(904, 'SIC', 3611, 4130, 3, 3612, 4131, 4),
(905, 'NAICS', 930, 42, 1, 942, 423210, 5),
(906, 'NAICS', 2136, 921, 2, 2142, 921130, 5),
(907, 'SIC', 3211, 2790, 3, 3212, 2791, 4),
(908, 'NAICS', 2037, 81, 1, 2108, 81321, 4),
(909, 'NAICS', 1402, 51, 1, 1476, 519130, 5),
(910, 'SIC', 3958, 6300, 2, 3962, 6321, 4),
(911, 'NAICS', 242, 23813, 4, 241, 238130, 5),
(912, 'SIC', 3338, 3310, 3, 3341, 3315, 4),
(913, 'SIC', 4310, 50, 1, 3718, 5013, 4),
(914, 'NAICS', 132, 21, 1, 174, 21311, 4),
(915, 'SIC', 3921, 6020, 3, 3922, 6021, 4),
(916, 'NAICS', 89, 1129, 3, 97, 11299, 4),
(917, 'SIC', 3220, 2820, 3, 3224, 2824, 4),
(918, 'SIC', 4313, 70, 1, 4189, 8249, 4),
(919, 'NAICS', 2037, 81, 1, 2074, 812111, 5),
(920, 'SIC', 4308, 20, 1, 3224, 2824, 4),
(921, 'SIC', 4313, 70, 1, 4112, 7699, 4),
(922, 'NAICS', 1, 11, 1, 27, 11132, 4),
(923, 'NAICS', 1942, 71, 1, 1961, 711320, 5),
(924, 'SEC', 2552, 4900, 2, 2562, 4940, 3),
(925, 'NAICS', 2177, 9241, 3, 2179, 92411, 4),
(926, 'SIC', 3124, 2400, 2, 3141, 2450, 3),
(927, 'NAICS', 1726, 561, 2, 1745, 561421, 5),
(928, 'NAICS', 2183, 9251, 3, 2186, 925120, 5),
(929, 'SIC', 3911, 5990, 3, 3915, 5995, 4),
(930, 'SIC', 3101, 2350, 3, 3102, 2353, 4),
(931, 'NAICS', 1741, 5614, 3, 1747, 56143, 4),
(932, 'NAICS', 2037, 81, 1, 2075, 812112, 5),
(933, 'SIC', 4178, 8200, 2, 4181, 8220, 3),
(934, 'NAICS', 1051, 42448, 4, 1050, 424480, 5),
(935, 'NAICS', 2135, 92, 1, 2150, 922, 2),
(936, 'SIC', 3797, 5190, 3, 3802, 5198, 4),
(937, 'SIC', 4311, 52, 1, 3848, 5560, 3),
(938, 'SIC', 2955, 1700, 2, 2967, 1751, 4),
(939, 'SIC', 3480, 3600, 2, 3507, 3660, 3),
(940, 'NAICS', 1015, 424, 2, 1060, 42459, 4),
(941, 'NAICS', 1625, 541, 2, 1675, 541612, 5),
(942, 'SIC', 4305, 1, 1, 2818, 175, 4),
(943, 'SIC', 2813, 170, 3, 2816, 173, 4),
(944, 'NAICS', 1402, 51, 1, 1458, 51721, 4),
(945, 'SIC', 4308, 20, 1, 3231, 2841, 4),
(946, 'SIC', 3258, 2990, 3, 3259, 2992, 4),
(947, 'NAICS', 1480, 52, 1, 1509, 522320, 5),
(948, 'NAICS', 1672, 5416, 3, 1673, 54161, 4),
(949, 'SIC', 4146, 8000, 2, 4150, 8021, 4),
(950, 'SEC', 2713, 7300, 2, 2727, 7372, 4),
(951, 'SEC', 2323, 2830, 3, 2324, 2833, 4),
(952, 'NAICS', 1942, 71, 1, 1978, 71219, 4),
(953, 'SIC', 3680, 4800, 2, 3689, 4840, 3),
(954, 'SIC', 3958, 6300, 2, 3968, 6360, 3),
(955, 'NAICS', 930, 42, 1, 1045, 42445, 4),
(956, 'SIC', 2982, 2000, 2, 3015, 2063, 4),
(957, 'NAICS', 181, 221, 2, 203, 221330, 5),
(958, 'SIC', 4305, 1, 1, 2846, 291, 4),
(959, 'SEC', 2789, 10, 1, 2224, 1380, 3),
(960, 'SIC', 3917, 6000, 2, 3936, 6099, 4),
(961, 'NAICS', 2037, 81, 1, 2098, 812922, 5),
(962, 'SIC', 3127, 2420, 3, 3130, 2429, 4),
(963, 'SEC', 2703, 6700, 2, 4327, 6770, 3),
(964, 'NAICS', 963, 42344, 4, 962, 423440, 5),
(965, 'SIC', 3050, 2200, 2, 3064, 2257, 4),
(966, 'SIC', 4081, 7500, 2, 4087, 7520, 3),
(967, 'SIC', 3419, 3500, 2, 3471, 3585, 4),
(968, 'SIC', 4309, 40, 1, 3710, 4959, 4),
(969, 'NAICS', 1806, 56291, 4, 1805, 562910, 5),
(970, 'SIC', 3911, 5990, 3, 3912, 5992, 4),
(971, 'SIC', 4307, 15, 1, 2971, 1770, 3),
(972, 'NAICS', 2183, 9251, 3, 2185, 92511, 4),
(973, 'SEC', 2552, 4900, 2, 2561, 4932, 4),
(974, 'NAICS', 1763, 56159, 4, 1765, 561599, 5),
(975, 'NAICS', 2167, 9231, 3, 2175, 92314, 4),
(976, 'SIC', 3287, 3140, 3, 3289, 3143, 4),
(977, 'NAICS', 1402, 51, 1, 1453, 5171, 3),
(978, 'NAICS', 1944, 7111, 3, 1945, 711110, 5),
(979, 'SIC', 2993, 2030, 3, 2995, 2033, 4),
(980, 'NAICS', 207, 2361, 3, 208, 23611, 4),
(981, 'SIC', 2973, 1780, 3, 2974, 1781, 4),
(982, 'SIC', 4308, 20, 1, 3091, 2326, 4),
(983, 'SIC', 3917, 6000, 2, 3935, 6091, 4),
(984, 'NAICS', 1605, 53229, 4, 1607, 532292, 5),
(985, 'NAICS', 1484, 52111, 4, 1483, 521110, 5),
(986, 'SEC', 2465, 3720, 3, 2468, 3728, 4),
(987, 'NAICS', 1979, 713, 2, 1995, 713930, 5),
(988, 'NAICS', 2188, 926, 2, 2195, 92613, 4),
(989, 'NAICS', 1943, 711, 2, 1949, 711130, 5),
(990, 'SEC', 2796, 70, 1, 2730, 7377, 4),
(991, 'NAICS', 930, 42, 1, 1046, 424460, 5),
(992, 'NAICS', 1850, 62, 1, 1872, 621410, 5),
(993, 'SIC', 4308, 20, 1, 3503, 3648, 4),
(994, 'SIC', 3237, 2860, 3, 3240, 2869, 4),
(995, 'SEC', 2555, 4920, 3, 2558, 4924, 4),
(996, 'SIC', 2982, 2000, 2, 2985, 2013, 4),
(997, 'NAICS', 1569, 53, 1, 1576, 531130, 5),
(998, 'SEC', 2371, 3300, 2, 2375, 3320, 3),
(999, 'SEC', 2758, 8060, 3, 2759, 8062, 4),
(1000, 'SIC', 4277, 9500, 2, 4281, 9530, 3),
(1001, 'SIC', 3621, 4210, 3, 3622, 4212, 4),
(1002, 'NAICS', 56, 112, 2, 76, 11234, 4),
(1003, 'SIC', 4312, 60, 1, 3984, 6519, 4),
(1004, 'NAICS', 1624, 54, 1, 1704, 541890, 5),
(1005, 'NAICS', 1, 11, 1, 77, 112390, 5),
(1006, 'NAICS', 2072, 8121, 3, 2079, 812199, 5),
(1007, 'SIC', 3444, 3550, 3, 3450, 3559, 4),
(1008, 'SIC', 3174, 2650, 3, 3179, 2657, 4),
(1009, 'NAICS', 1, 11, 1, 125, 115116, 5),
(1010, 'NAICS', 1076, 4249, 3, 1080, 42492, 4),
(1011, 'SIC', 3368, 3390, 3, 3370, 3399, 4),
(1012, 'SEC', 2791, 20, 1, 2387, 3412, 4),
(1013, 'SIC', 4309, 40, 1, 3691, 4890, 3),
(1014, 'SIC', 3942, 6150, 3, 3944, 6159, 4),
(1015, 'NAICS', 1466, 518, 2, 1468, 518210, 5),
(1016, 'NAICS', 1851, 621, 2, 1853, 62111, 4),
(1017, 'SIC', 4310, 50, 1, 3738, 5051, 4),
(1018, 'SIC', 4308, 20, 1, 3109, 2381, 4),
(1019, 'NAICS', 1402, 51, 1, 1468, 518210, 5),
(1020, 'SEC', 2792, 40, 1, 2557, 4923, 4),
(1021, 'SIC', 2909, 1300, 2, 2910, 1310, 3),
(1022, 'SIC', 4171, 8090, 3, 4173, 8093, 4),
(1023, 'NAICS', 83, 11242, 4, 82, 112420, 5),
(1024, 'NAICS', 23, 1113, 3, 27, 11132, 4),
(1025, 'SIC', 3837, 5500, 2, 3845, 5541, 4),
(1026, 'SEC', 2459, 3710, 3, 2460, 3711, 4),
(1027, 'SIC', 4305, 1, 1, 2853, 723, 4),
(1028, 'NAICS', 1, 11, 1, 20, 11121, 4),
(1029, 'NAICS', 1942, 71, 1, 1964, 711410, 5),
(1030, 'SIC', 3829, 5440, 3, 3830, 5441, 4),
(1031, 'NAICS', 180, 22, 1, 202, 22132, 4),
(1032, 'SEC', 2753, 8000, 2, 2764, 8090, 3),
(1033, 'SIC', 4312, 60, 1, 3953, 6230, 3),
(1034, 'SEC', 2271, 2300, 2, 2274, 2340, 3),
(1035, 'SIC', 4284, 9600, 2, 4290, 9631, 4),
(1036, 'NAICS', 2039, 8111, 3, 2041, 811111, 5),
(1037, 'SEC', 2713, 7300, 2, 2718, 7331, 4),
(1038, 'NAICS', 2038, 811, 2, 2059, 811310, 5),
(1039, 'NAICS', 2038, 811, 2, 2049, 811191, 5),
(1040, 'SIC', 4305, 1, 1, 2808, 133, 4),
(1041, 'SIC', 4308, 20, 1, 3089, 2323, 4),
(1042, 'SIC', 4313, 70, 1, 4056, 7342, 4),
(1043, 'NAICS', 2169, 92311, 4, 2168, 923110, 5),
(1044, 'SIC', 4175, 8100, 2, 4177, 8111, 4),
(1045, 'NAICS', 2161, 92215, 4, 2160, 922150, 5),
(1046, 'SEC', 2791, 20, 1, 2292, 2600, 2),
(1047, 'NAICS', 1500, 52229, 4, 1505, 522298, 5),
(1048, 'SIC', 3426, 3530, 3, 3432, 3536, 4),
(1049, 'SIC', 2975, 1790, 3, 2976, 1791, 4),
(1050, 'SIC', 4308, 20, 1, 3511, 3670, 3),
(1051, 'SIC', 3167, 2600, 2, 3171, 2621, 4),
(1052, 'NAICS', 1942, 71, 1, 1952, 71119, 4),
(1053, 'SEC', 2500, 3900, 2, 2509, 3950, 3),
(1054, 'NAICS', 2089, 81232, 4, 2088, 812320, 5),
(1055, 'NAICS', 1600, 53221, 4, 1599, 532210, 5),
(1056, 'SEC', 2791, 20, 1, 2464, 3716, 4),
(1057, 'SIC', 3214, 2800, 2, 3221, 2821, 4),
(1058, 'SIC', 4100, 7600, 2, 4104, 7629, 4),
(1059, 'SIC', 3266, 3050, 3, 3268, 3053, 4),
(1060, 'SIC', 4308, 20, 1, 3267, 3052, 4),
(1061, 'SIC', 4311, 52, 1, 3827, 5430, 3),
(1062, 'SEC', 2796, 70, 1, 2724, 7363, 4),
(1063, 'NAICS', 1979, 713, 2, 1994, 71392, 4),
(1064, 'NAICS', 129, 1153, 3, 131, 11531, 4),
(1065, 'NAICS', 1061, 4246, 3, 1063, 42461, 4),
(1066, 'NAICS', 2037, 81, 1, 2090, 81233, 4),
(1067, 'NAICS', 2071, 812, 2, 2101, 812990, 5),
(1068, 'SIC', 4305, 1, 1, 2805, 130, 3),
(1069, 'NAICS', 206, 236, 2, 208, 23611, 4),
(1070, 'SIC', 3825, 5420, 3, 3826, 5421, 4),
(1071, 'NAICS', 2072, 8121, 3, 2078, 812191, 5),
(1072, 'SIC', 4308, 20, 1, 3490, 3631, 4),
(1073, 'SIC', 4308, 20, 1, 3341, 3315, 4),
(1074, 'SEC', 2791, 20, 1, 2253, 2070, 3),
(1075, 'SEC', 2458, 3700, 2, 2467, 3724, 4),
(1076, 'NAICS', 56, 112, 2, 79, 1124, 3),
(1077, 'NAICS', 181, 221, 2, 194, 221122, 5),
(1078, 'SEC', 2418, 3560, 3, 2423, 3569, 4),
(1079, 'NAICS', 2135, 92, 1, 2196, 926140, 5),
(1080, 'SEC', 2435, 3610, 3, 2437, 3613, 4),
(1081, 'SEC', 2633, 5730, 3, 2634, 5731, 4),
(1082, 'SEC', 2791, 20, 1, 2383, 3390, 3),
(1083, 'NAICS', 2, 111, 2, 33, 111335, 5),
(1084, 'NAICS', 1741, 5614, 3, 1746, 561422, 5),
(1085, 'NAICS', 1625, 541, 2, 1643, 541320, 5),
(1086, 'NAICS', 2038, 811, 2, 2040, 81111, 4),
(1087, 'SIC', 3141, 2450, 3, 3142, 2451, 4),
(1088, 'SIC', 4308, 20, 1, 3031, 2086, 4),
(1089, 'NAICS', 1, 11, 1, 71, 112320, 5),
(1090, 'SEC', 2254, 2080, 3, 2255, 2082, 4),
(1091, 'SIC', 4313, 70, 1, 4055, 7340, 3),
(1092, 'NAICS', 1850, 62, 1, 1940, 624410, 5),
(1093, 'NAICS', 1706, 5419, 3, 1711, 541922, 5),
(1094, 'SIC', 4313, 70, 1, 4035, 7260, 3),
(1095, 'NAICS', 132, 21, 1, 134, 2111, 3),
(1096, 'NAICS', 43, 1119, 3, 45, 11191, 4),
(1097, 'NAICS', 2112, 8133, 3, 2114, 813311, 5),
(1098, 'SIC', 4146, 8000, 2, 4151, 8030, 3),
(1099, 'NAICS', 1536, 524, 2, 1545, 524130, 5),
(1100, 'SIC', 4311, 52, 1, 3833, 5460, 3),
(1101, 'SIC', 3392, 3450, 3, 3393, 3451, 4),
(1102, 'SIC', 3371, 3400, 2, 3415, 3496, 4),
(1103, 'SIC', 4312, 60, 1, 3934, 6090, 3),
(1104, 'SIC', 2955, 1700, 2, 2977, 1793, 4),
(1105, 'SEC', 2649, 6000, 2, 2651, 6021, 4),
(1106, 'SIC', 3167, 2600, 2, 3189, 2679, 4),
(1107, 'SIC', 3822, 5400, 2, 3834, 5461, 4),
(1108, 'SIC', 4017, 7200, 2, 4034, 7251, 4),
(1109, 'NAICS', 1428, 51219, 4, 1429, 512191, 5),
(1110, 'SEC', 2791, 20, 1, 2404, 3510, 3),
(1111, 'SIC', 4314, 90, 1, 4271, 9430, 3),
(1112, 'NAICS', 1480, 52, 1, 1513, 523, 2),
(1113, 'SEC', 2796, 70, 1, 2753, 8000, 2),
(1114, 'SEC', 2796, 70, 1, 2767, 8110, 3),
(1115, 'SIC', 3507, 3660, 3, 3508, 3661, 4),
(1116, 'NAICS', 101, 11311, 4, 100, 113110, 5),
(1117, 'SIC', 4308, 20, 1, 3337, 3300, 2),
(1118, 'SIC', 3255, 2950, 3, 3256, 2951, 4),
(1119, 'SIC', 4305, 1, 1, 2879, 919, 4),
(1120, 'SIC', 4308, 20, 1, 3588, 3951, 4),
(1121, 'SIC', 4158, 8050, 3, 4161, 8059, 4),
(1122, 'NAICS', 2031, 7225, 3, 2033, 722511, 5),
(1123, 'SIC', 4125, 7900, 2, 4128, 7920, 3),
(1124, 'SEC', 2791, 20, 1, 2369, 3281, 4),
(1125, 'SIC', 3526, 3700, 2, 3528, 3711, 4),
(1126, 'NAICS', 1667, 54151, 4, 1669, 541512, 5),
(1127, 'NAICS', 1719, 551, 2, 1721, 55111, 4),
(1128, 'SIC', 3917, 6000, 2, 3933, 6082, 4),
(1129, 'SIC', 4081, 7500, 2, 4095, 7538, 4),
(1130, 'SIC', 4113, 7800, 2, 4115, 7812, 4),
(1131, 'NAICS', 1683, 5417, 3, 1688, 54172, 4),
(1132, 'SIC', 4313, 70, 1, 4145, 7999, 4),
(1133, 'SEC', 2791, 20, 1, 2252, 2060, 3),
(1134, 'SIC', 3654, 4500, 2, 3659, 4522, 4),
(1135, 'SIC', 3660, 4580, 3, 3661, 4581, 4),
(1136, 'NAICS', 1706, 5419, 3, 1716, 541990, 5),
(1137, 'SIC', 4311, 52, 1, 3893, 5940, 3),
(1138, 'SIC', 2847, 700, 2, 2852, 722, 4),
(1139, 'SEC', 2559, 4930, 3, 2561, 4932, 4),
(1140, 'SIC', 4312, 60, 1, 3980, 6513, 4),
(1141, 'SIC', 4309, 40, 1, 3662, 4600, 2),
(1142, 'SEC', 2384, 3400, 2, 2391, 3440, 3),
(1143, 'NAICS', 955, 4234, 3, 963, 42344, 4),
(1144, 'NAICS', 1820, 6113, 3, 1821, 611310, 5),
(1145, 'SIC', 3837, 5500, 2, 3839, 5511, 4),
(1146, 'SIC', 2928, 1450, 3, 2930, 1459, 4),
(1147, 'NAICS', 1015, 424, 2, 1085, 424950, 5),
(1148, 'NAICS', 2136, 921, 2, 2141, 92112, 4),
(1149, 'NAICS', 1706, 5419, 3, 1709, 54192, 4),
(1150, 'NAICS', 1792, 562, 2, 1803, 562219, 5),
(1151, 'SIC', 4313, 70, 1, 4146, 8000, 2),
(1152, 'NAICS', 1954, 71121, 4, 1957, 711219, 5),
(1153, 'SIC', 2847, 700, 2, 2861, 760, 3),
(1154, 'NAICS', 931, 423, 2, 949, 423320, 5),
(1155, 'NAICS', 2073, 81211, 4, 2076, 812113, 5),
(1156, 'NAICS', 1625, 541, 2, 1695, 54183, 4),
(1157, 'SEC', 2789, 10, 1, 2216, 1040, 3),
(1158, 'NAICS', 236, 2381, 3, 251, 238190, 5),
(1159, 'NAICS', 1624, 54, 1, 1690, 541810, 5),
(1160, 'NAICS', 1851, 621, 2, 1887, 62161, 4),
(1161, 'NAICS', 2061, 8114, 3, 2068, 81143, 4),
(1162, 'SIC', 2982, 2000, 2, 2994, 2032, 4),
(1163, 'NAICS', 1480, 52, 1, 1486, 5221, 3),
(1164, 'SEC', 2670, 6200, 2, 2674, 6221, 4),
(1165, 'SIC', 4311, 52, 1, 3908, 5983, 4),
(1166, 'NAICS', 2005, 7211, 3, 2006, 721110, 5),
(1167, 'SEC', 2424, 3570, 3, 2426, 3572, 4),
(1168, 'SEC', 2703, 6700, 2, 2707, 6798, 4),
(1169, 'NAICS', 2037, 81, 1, 2050, 811192, 5),
(1170, 'SEC', 2791, 20, 1, 2278, 2421, 4),
(1171, 'NAICS', 138, 212, 2, 144, 2122, 3),
(1172, 'NAICS', 2136, 921, 2, 2143, 92113, 4),
(1173, 'SIC', 4081, 7500, 2, 4091, 7533, 4),
(1174, 'SEC', 2792, 40, 1, 2546, 4832, 4),
(1175, 'NAICS', 2151, 9221, 3, 2154, 922120, 5),
(1176, 'NAICS', 1014, 42399, 4, 1013, 423990, 5),
(1177, 'NAICS', 930, 42, 1, 995, 42382, 4),
(1178, 'SIC', 3012, 2060, 3, 3018, 2067, 4),
(1179, 'SIC', 2820, 180, 3, 2821, 181, 4),
(1180, 'NAICS', 2103, 813, 2, 2119, 81341, 4),
(1181, 'SIC', 3026, 2080, 3, 3031, 2086, 4),
(1182, 'NAICS', 1043, 42444, 4, 1042, 424440, 5),
(1183, 'SIC', 4306, 10, 1, 2893, 1044, 4),
(1184, 'NAICS', 1953, 7112, 3, 1955, 711211, 5),
(1185, 'SEC', 2791, 20, 1, 2487, 3829, 4),
(1186, 'SIC', 4313, 70, 1, 4137, 7951, 4),
(1187, 'NAICS', 89, 1129, 3, 90, 112910, 5),
(1188, 'NAICS', 138, 212, 2, 147, 21222, 4),
(1189, 'SIC', 4308, 20, 1, 3446, 3553, 4),
(1190, 'NAICS', 1, 11, 1, 128, 11521, 4),
(1191, 'NAICS', 205, 23, 1, 214, 236210, 5),
(1192, 'SIC', 4275, 9450, 3, 4276, 9451, 4),
(1193, 'SEC', 2793, 50, 1, 2572, 5030, 3),
(1194, 'SIC', 2987, 2020, 3, 2992, 2026, 4),
(1195, 'NAICS', 1015, 424, 2, 1051, 42448, 4),
(1196, 'SIC', 4308, 20, 1, 3019, 2068, 4),
(1197, 'SEC', 2649, 6000, 2, 2655, 6035, 4),
(1198, 'SIC', 4309, 40, 1, 3635, 4311, 4),
(1199, 'NAICS', 1785, 5619, 3, 1787, 56191, 4),
(1200, 'SIC', 4310, 50, 1, 3803, 5199, 4),
(1201, 'NAICS', 84, 1125, 3, 88, 112519, 5),
(1202, 'NAICS', 183, 22111, 4, 187, 221114, 5),
(1203, 'NAICS', 2096, 81292, 4, 2098, 812922, 5),
(1204, 'NAICS', 1604, 53223, 4, 1603, 532230, 5),
(1205, 'NAICS', 1706, 5419, 3, 1714, 541940, 5),
(1206, 'NAICS', 43, 1119, 3, 49, 11193, 4),
(1207, 'NAICS', 931, 423, 2, 1006, 42391, 4),
(1208, 'NAICS', 2135, 92, 1, 2138, 921110, 5),
(1209, 'SIC', 4245, 8990, 3, 4246, 8999, 4),
(1210, 'NAICS', 1528, 52391, 4, 1527, 523910, 5),
(1211, 'NAICS', 1970, 7121, 3, 1976, 71213, 4),
(1212, 'SIC', 4311, 52, 1, 3880, 5735, 4),
(1213, 'SIC', 4308, 20, 1, 3259, 2992, 4),
(1214, 'NAICS', 7, 11112, 4, 6, 111120, 5),
(1215, 'NAICS', 1990, 7139, 3, 2001, 713990, 5),
(1216, 'SIC', 4308, 20, 1, 3439, 3545, 4),
(1217, 'NAICS', 1894, 622, 2, 1897, 62211, 4),
(1218, 'SEC', 2791, 20, 1, 2303, 2710, 3),
(1219, 'SIC', 4313, 70, 1, 4010, 7020, 3),
(1220, 'NAICS', 1591, 532, 2, 1595, 532112, 5),
(1221, 'NAICS', 1626, 5411, 3, 1631, 54119, 4),
(1222, 'NAICS', 2039, 8111, 3, 2047, 811122, 5),
(1223, 'NAICS', 1480, 52, 1, 1567, 525990, 5),
(1224, 'NAICS', 2003, 72, 1, 2016, 721214, 5),
(1225, 'SIC', 3893, 5940, 3, 3895, 5942, 4),
(1226, 'NAICS', 1431, 5122, 3, 1440, 512290, 5),
(1227, 'SIC', 3667, 4700, 2, 3669, 4724, 4),
(1228, 'NAICS', 2021, 7223, 3, 2025, 72232, 4),
(1229, 'NAICS', 2037, 81, 1, 2058, 8113, 3),
(1230, 'SEC', 2791, 20, 1, 2492, 3844, 4),
(1231, 'NAICS', 1571, 5311, 3, 1578, 531190, 5),
(1232, 'SIC', 4308, 20, 1, 3147, 2499, 4),
(1233, 'SIC', 3917, 6000, 2, 3920, 6019, 4),
(1234, 'SEC', 2791, 20, 1, 2482, 3823, 4),
(1235, 'SIC', 4308, 20, 1, 3149, 2510, 3),
(1236, 'SEC', 2794, 52, 1, 2621, 5530, 3),
(1237, 'SIC', 3225, 2830, 3, 3226, 2833, 4),
(1238, 'NAICS', 1015, 424, 2, 1022, 42413, 4),
(1239, 'SIC', 4313, 70, 1, 4048, 7323, 4),
(1240, 'SIC', 3613, 4140, 3, 3614, 4141, 4),
(1241, 'SIC', 3948, 6200, 2, 3953, 6230, 3),
(1242, 'NAICS', 2037, 81, 1, 2125, 813930, 5),
(1243, 'SIC', 4136, 7950, 3, 4138, 7952, 4),
(1244, 'NAICS', 36, 1114, 3, 37, 11141, 4),
(1245, 'SIC', 3844, 5540, 3, 3845, 5541, 4),
(1246, 'SIC', 4309, 40, 1, 3648, 4489, 4),
(1247, 'NAICS', 1569, 53, 1, 1609, 5323, 3),
(1248, 'SIC', 4308, 20, 1, 3569, 3845, 4),
(1249, 'SIC', 3434, 3540, 3, 3437, 3543, 4),
(1250, 'SIC', 4312, 60, 1, 3921, 6020, 3),
(1251, 'NAICS', 98, 113, 2, 102, 1132, 3),
(1252, 'NAICS', 1865, 62133, 4, 1864, 621330, 5),
(1253, 'SEC', 2794, 52, 1, 2645, 5945, 4),
(1254, 'NAICS', 2037, 81, 1, 2068, 81143, 4),
(1255, 'NAICS', 1725, 56, 1, 1743, 56141, 4),
(1256, 'NAICS', 2150, 922, 2, 2152, 922110, 5),
(1257, 'SIC', 2891, 1040, 3, 2893, 1044, 4),
(1258, 'NAICS', 1402, 51, 1, 1457, 517210, 5),
(1259, 'NAICS', 1850, 62, 1, 1897, 62211, 4),
(1260, 'SIC', 3083, 2300, 2, 3118, 2393, 4),
(1261, 'SIC', 3253, 2910, 3, 3254, 2911, 4),
(1262, 'SEC', 2403, 3500, 2, 2404, 3510, 3),
(1263, 'SIC', 3371, 3400, 2, 3406, 3483, 4),
(1264, 'NAICS', 1569, 53, 1, 1596, 532120, 5),
(1265, 'NAICS', 1689, 5418, 3, 1695, 54183, 4),
(1266, 'SIC', 4046, 7320, 3, 4048, 7323, 4),
(1267, 'NAICS', 1942, 71, 1, 1967, 711510, 5),
(1268, 'SEC', 2431, 3580, 3, 2432, 3585, 4),
(1269, 'SIC', 3626, 4220, 3, 3630, 4226, 4),
(1270, 'SIC', 4128, 7920, 3, 4130, 7929, 4),
(1271, 'NAICS', 982, 4237, 3, 990, 42374, 4),
(1272, 'SIC', 3124, 2400, 2, 3126, 2411, 4),
(1273, 'SIC', 4313, 70, 1, 4157, 8049, 4),
(1274, 'NAICS', 157, 21231, 4, 161, 212319, 5),
(1275, 'SIC', 4313, 70, 1, 4028, 7221, 4),
(1276, 'SIC', 4313, 70, 1, 4175, 8100, 2),
(1277, 'NAICS', 1485, 522, 2, 1492, 52213, 4),
(1278, 'SIC', 3344, 3320, 3, 3348, 3325, 4),
(1279, 'SIC', 3715, 5000, 2, 3741, 5063, 4),
(1280, 'SEC', 2789, 10, 1, 2220, 1221, 4),
(1281, 'NAICS', 1402, 51, 1, 1408, 51112, 4),
(1282, 'NAICS', 2203, 92711, 4, 2202, 927110, 5),
(1283, 'NAICS', 931, 423, 2, 954, 42339, 4),
(1284, 'SIC', 3041, 2100, 2, 3049, 2141, 4),
(1285, 'SIC', 4311, 52, 1, 3841, 5521, 4),
(1286, 'NAICS', 1, 11, 1, 17, 111191, 5),
(1287, 'NAICS', 117, 115, 2, 130, 115310, 5),
(1288, 'NAICS', 984, 42371, 4, 983, 423710, 5),
(1289, 'SIC', 4308, 20, 1, 3391, 3449, 4),
(1290, 'NAICS', 1442, 515, 2, 1444, 51511, 4),
(1291, 'SEC', 2796, 70, 1, 2778, 8731, 4),
(1292, 'NAICS', 138, 212, 2, 159, 212312, 5),
(1293, 'NAICS', 1620, 533, 2, 1623, 53311, 4),
(1294, 'NAICS', 1402, 51, 1, 1416, 5112, 3),
(1295, 'NAICS', 1624, 54, 1, 1665, 54149, 4),
(1296, 'SEC', 2408, 3530, 3, 2409, 3531, 4),
(1297, 'NAICS', 182, 2211, 3, 193, 221121, 5),
(1298, 'NAICS', 930, 42, 1, 1026, 4243, 3),
(1299, 'SIC', 3380, 3430, 3, 3381, 3431, 4),
(1300, 'NAICS', 1812, 61, 1, 1839, 611620, 5),
(1301, 'SEC', 2795, 60, 1, 2675, 6280, 3),
(1302, 'NAICS', 1812, 61, 1, 1815, 611110, 5),
(1303, 'SIC', 4308, 20, 1, 3057, 2240, 3),
(1304, 'SIC', 3371, 3400, 2, 3389, 3446, 4),
(1305, 'NAICS', 2080, 8122, 3, 2083, 812220, 5),
(1306, 'SEC', 2283, 2500, 2, 2288, 2530, 3),
(1307, 'SIC', 3461, 3570, 3, 3462, 3571, 4),
(1308, 'NAICS', 57, 1121, 3, 59, 112111, 5),
(1309, 'NAICS', 1990, 7139, 3, 1991, 713910, 5),
(1310, 'SIC', 2948, 1600, 2, 2949, 1610, 3),
(1311, 'SIC', 4309, 40, 1, 3694, 4910, 3),
(1312, 'SIC', 2826, 210, 3, 2831, 219, 4),
(1313, 'SEC', 2796, 70, 1, 2771, 8350, 3),
(1314, 'SIC', 4146, 8000, 2, 4164, 8063, 4),
(1315, 'SIC', 4305, 1, 1, 2824, 191, 4),
(1316, 'NAICS', 1570, 531, 2, 1582, 53121, 4),
(1317, 'SIC', 4308, 20, 1, 3069, 2262, 4),
(1318, 'NAICS', 2095, 81291, 4, 2094, 812910, 5),
(1319, 'SIC', 3903, 5960, 3, 3906, 5963, 4),
(1320, 'SIC', 3917, 6000, 2, 3927, 6036, 4),
(1321, 'SIC', 3917, 6000, 2, 3928, 6060, 3),
(1322, 'NAICS', 198, 2213, 3, 201, 221320, 5),
(1323, 'NAICS', 1015, 424, 2, 1018, 42411, 4),
(1324, 'SEC', 2496, 3860, 3, 2497, 3861, 4),
(1325, 'SIC', 3999, 6730, 3, 4000, 6732, 4),
(1326, 'NAICS', 1, 11, 1, 37, 11141, 4),
(1327, 'NAICS', 1625, 541, 2, 1669, 541512, 5),
(1328, 'SIC', 4308, 20, 1, 3330, 3290, 3),
(1329, 'SIC', 3174, 2650, 3, 3176, 2653, 4),
(1330, 'SEC', 2476, 3800, 2, 2479, 3820, 3),
(1331, 'SIC', 4308, 20, 1, 3350, 3331, 4),
(1332, 'NAICS', 1404, 5111, 3, 1405, 511110, 5),
(1333, 'NAICS', 2013, 7212, 3, 2014, 72121, 4),
(1334, 'NAICS', 1004, 4239, 3, 1010, 42393, 4),
(1335, 'SIC', 3715, 5000, 2, 3756, 5090, 3),
(1336, 'NAICS', 2004, 721, 2, 2011, 721191, 5),
(1337, 'NAICS', 1546, 52413, 4, 1545, 524130, 5),
(1338, 'NAICS', 2102, 81299, 4, 2101, 812990, 5),
(1339, 'SIC', 4309, 40, 1, 3659, 4522, 4),
(1340, 'SIC', 4313, 70, 1, 4198, 8351, 4),
(1341, 'NAICS', 1813, 611, 2, 1842, 61163, 4),
(1342, 'SIC', 4308, 20, 1, 3359, 3355, 4),
(1343, 'SIC', 4313, 70, 1, 4089, 7530, 3),
(1344, 'SIC', 3715, 5000, 2, 3746, 5074, 4),
(1345, 'SIC', 3581, 3930, 3, 3582, 3931, 4),
(1346, 'NAICS', 2037, 81, 1, 2055, 811212, 5),
(1347, 'NAICS', 2151, 9221, 3, 2153, 92211, 4),
(1348, 'SIC', 2982, 2000, 2, 3040, 2099, 4),
(1349, 'NAICS', 930, 42, 1, 974, 42352, 4),
(1350, 'NAICS', 1424, 51212, 4, 1423, 512120, 5),
(1351, 'NAICS', 1634, 5412, 3, 1635, 54121, 4),
(1352, 'SIC', 4312, 60, 1, 3944, 6159, 4),
(1353, 'SIC', 4313, 70, 1, 4129, 7922, 4),
(1354, 'SEC', 2792, 40, 1, 2549, 4841, 4),
(1355, 'SIC', 3762, 5100, 2, 3801, 5194, 4),
(1356, 'NAICS', 182, 2211, 3, 186, 221113, 5),
(1357, 'SEC', 2568, 5000, 2, 2577, 5050, 3),
(1358, 'NAICS', 1592, 5321, 3, 1596, 532120, 5),
(1359, 'NAICS', 2108, 81321, 4, 2110, 813212, 5),
(1360, 'SIC', 2868, 800, 2, 2872, 831, 4),
(1361, 'NAICS', 2037, 81, 1, 2091, 812331, 5),
(1362, 'SIC', 4308, 20, 1, 3561, 3826, 4),
(1363, 'SIC', 3724, 5030, 3, 3725, 5031, 4),
(1364, 'NAICS', 2189, 9261, 3, 2191, 92611, 4),
(1365, 'SEC', 2795, 60, 1, 2690, 6399, 4),
(1366, 'NAICS', 1942, 71, 1, 1955, 711211, 5),
(1367, 'SEC', 2791, 20, 1, 2282, 2452, 4),
(1368, 'SIC', 3349, 3330, 3, 3351, 3334, 4),
(1369, 'SIC', 4203, 8400, 2, 4206, 8420, 3),
(1370, 'NAICS', 181, 221, 2, 190, 221117, 5),
(1371, 'NAICS', 1583, 5313, 3, 1584, 53131, 4),
(1372, 'NAICS', 1532, 52393, 4, 1531, 523930, 5),
(1373, 'SIC', 3544, 3760, 3, 3546, 3764, 4),
(1374, 'NAICS', 1402, 51, 1, 1417, 511210, 5),
(1375, 'NAICS', 208, 23611, 4, 211, 236117, 5),
(1376, 'SIC', 4313, 70, 1, 4105, 7630, 3),
(1377, 'NAICS', 930, 42, 1, 935, 423120, 5),
(1378, 'SEC', 2742, 7820, 3, 2743, 7822, 4),
(1379, 'NAICS', 930, 42, 1, 1065, 42469, 4),
(1380, 'NAICS', 930, 42, 1, 937, 423130, 5),
(1381, 'SIC', 2921, 1420, 3, 2924, 1429, 4),
(1382, 'SIC', 4308, 20, 1, 3303, 3211, 4),
(1383, 'SIC', 4308, 20, 1, 3241, 2870, 3),
(1384, 'SIC', 2876, 910, 3, 2877, 912, 4),
(1385, 'NAICS', 2135, 92, 1, 2172, 923130, 5),
(1386, 'SIC', 3511, 3670, 3, 3516, 3676, 4),
(1387, 'SIC', 3937, 6100, 2, 3940, 6140, 3),
(1388, 'NAICS', 236, 2381, 3, 241, 238130, 5),
(1389, 'NAICS', 2037, 81, 1, 2059, 811310, 5),
(1390, 'NAICS', 2037, 81, 1, 2049, 811191, 5),
(1391, 'NAICS', 56, 112, 2, 90, 112910, 5),
(1392, 'SIC', 4313, 70, 1, 4057, 7349, 4),
(1393, 'SEC', 2403, 3500, 2, 2423, 3569, 4),
(1394, 'SIC', 4308, 20, 1, 3148, 2500, 2),
(1395, 'NAICS', 56, 112, 2, 59, 112111, 5),
(1396, 'NAICS', 205, 23, 1, 221, 23711, 4),
(1397, 'NAICS', 2003, 72, 1, 2013, 7212, 3),
(1398, 'SIC', 3715, 5000, 2, 3716, 5010, 3),
(1399, 'SIC', 3701, 4930, 3, 3703, 4932, 4),
(1400, 'SIC', 3940, 6140, 3, 3941, 6141, 4),
(1401, 'SIC', 4309, 40, 1, 3625, 4215, 4),
(1402, 'SIC', 4311, 52, 1, 3855, 5610, 3),
(1403, 'NAICS', 2037, 81, 1, 2126, 81393, 4),
(1404, 'SEC', 2476, 3800, 2, 2486, 3827, 4),
(1405, 'NAICS', 1536, 524, 2, 1537, 5241, 3),
(1406, 'SIC', 3419, 3500, 2, 3475, 3592, 4),
(1407, 'NAICS', 1470, 519, 2, 1474, 519120, 5),
(1408, 'SIC', 3012, 2060, 3, 3017, 2066, 4),
(1409, 'NAICS', 226, 2372, 3, 228, 23721, 4),
(1410, 'SIC', 3050, 2200, 2, 3058, 2241, 4),
(1411, 'NAICS', 1049, 42447, 4, 1048, 424470, 5),
(1412, 'NAICS', 1908, 6232, 3, 1910, 62321, 4),
(1413, 'NAICS', 2, 111, 2, 24, 111310, 5),
(1414, 'SEC', 2791, 20, 1, 2354, 3140, 3),
(1415, 'NAICS', 180, 22, 1, 181, 221, 2),
(1416, 'SIC', 2813, 170, 3, 2814, 171, 4),
(1417, 'NAICS', 991, 4238, 3, 995, 42382, 4),
(1418, 'NAICS', 931, 423, 2, 970, 4235, 3),
(1419, 'NAICS', 1726, 561, 2, 1756, 561492, 5),
(1420, 'SIC', 2901, 1200, 2, 2907, 1240, 3),
(1421, 'NAICS', 2037, 81, 1, 2115, 813312, 5),
(1422, 'SEC', 2791, 20, 1, 2260, 2110, 3),
(1423, 'SIC', 3020, 2070, 3, 3025, 2079, 4),
(1424, 'NAICS', 931, 423, 2, 996, 423830, 5),
(1425, 'NAICS', 2, 111, 2, 32, 111334, 5),
(1426, 'NAICS', 1725, 56, 1, 1791, 56199, 4),
(1427, 'NAICS', 181, 221, 2, 192, 22112, 4),
(1428, 'NAICS', 2037, 81, 1, 2113, 81331, 4),
(1429, 'NAICS', 1725, 56, 1, 1807, 562920, 5),
(1430, 'SIC', 3526, 3700, 2, 3550, 3795, 4),
(1431, 'SEC', 2685, 6350, 3, 2686, 6351, 4),
(1432, 'NAICS', 2037, 81, 1, 2040, 81111, 4),
(1433, 'SIC', 3680, 4800, 2, 3688, 4833, 4),
(1434, 'NAICS', 1825, 61141, 4, 1824, 611410, 5),
(1435, 'SIC', 3882, 5800, 2, 3883, 5810, 3),
(1436, 'SIC', 4312, 60, 1, 3988, 6541, 4),
(1437, 'SIC', 4306, 10, 1, 2922, 1422, 4),
(1438, 'NAICS', 205, 23, 1, 218, 237, 2),
(1439, 'NAICS', 1082, 42493, 4, 1081, 424930, 5),
(1440, 'SIC', 3468, 3580, 3, 3470, 3582, 4),
(1441, 'SIC', 4312, 60, 1, 4006, 6799, 4),
(1442, 'SIC', 4307, 15, 1, 2964, 1742, 4),
(1443, 'SIC', 4308, 20, 1, 3433, 3537, 4),
(1444, 'NAICS', 1431, 5122, 3, 1438, 512240, 5),
(1445, 'NAICS', 1569, 53, 1, 1583, 5313, 3),
(1446, 'NAICS', 2009, 72112, 4, 2008, 721120, 5),
(1447, 'SIC', 4308, 20, 1, 3355, 3350, 3),
(1448, 'NAICS', 1547, 5242, 3, 1550, 52429, 4),
(1449, 'NAICS', 1402, 51, 1, 1450, 515210, 5),
(1450, 'NAICS', 1787, 56191, 4, 1786, 561910, 5),
(1451, 'SEC', 2583, 5070, 3, 2584, 5072, 4),
(1452, 'SIC', 2982, 2000, 2, 2984, 2011, 4),
(1453, 'SIC', 4308, 20, 1, 3524, 3695, 4),
(1454, 'SIC', 3371, 3400, 2, 3378, 3425, 4),
(1455, 'NAICS', 931, 423, 2, 946, 4233, 3),
(1456, 'SEC', 2796, 70, 1, 2779, 8734, 4),
(1457, 'SIC', 4306, 10, 1, 2929, 1455, 4),
(1458, 'SIC', 3555, 3820, 3, 3556, 3821, 4),
(1459, 'NAICS', 2085, 8123, 3, 2088, 812320, 5),
(1460, 'SEC', 2793, 50, 1, 2579, 5060, 3),
(1461, 'SIC', 3296, 3170, 3, 3297, 3171, 4),
(1462, 'NAICS', 1537, 5241, 3, 1540, 524114, 5),
(1463, 'NAICS', 1015, 424, 2, 1046, 424460, 5),
(1464, 'NAICS', 1004, 4239, 3, 1012, 42394, 4),
(1465, 'NAICS', 2135, 92, 1, 2180, 924120, 5),
(1466, 'SIC', 2902, 1220, 3, 2904, 1222, 4),
(1467, 'SEC', 2380, 3350, 3, 2381, 3357, 4),
(1468, 'SEC', 2434, 3600, 2, 2445, 3652, 4),
(1469, 'SEC', 2704, 6790, 3, 2707, 6798, 4),
(1470, 'NAICS', 1, 11, 1, 5, 11111, 4),
(1471, 'SIC', 3419, 3500, 2, 3478, 3596, 4),
(1472, 'SEC', 2260, 2110, 3, 2261, 2111, 4),
(1473, 'SIC', 3715, 5000, 2, 3735, 5048, 4),
(1474, 'NAICS', 2084, 81222, 4, 2083, 812220, 5),
(1475, 'SIC', 3886, 5900, 2, 3891, 5930, 3),
(1476, 'NAICS', 931, 423, 2, 997, 42383, 4),
(1477, 'SEC', 2670, 6200, 2, 2675, 6280, 3),
(1478, 'SIC', 4308, 20, 1, 3141, 2450, 3),
(1479, 'SIC', 3605, 4100, 2, 3619, 4173, 4),
(1480, 'NAICS', 1480, 52, 1, 1496, 522210, 5),
(1481, 'SIC', 3093, 2330, 3, 3097, 2339, 4),
(1482, 'SIC', 2918, 1400, 2, 2921, 1420, 3),
(1483, 'SIC', 3854, 5600, 2, 3863, 5650, 3),
(1484, 'SIC', 4313, 70, 1, 4029, 7230, 3),
(1485, 'SIC', 3676, 4780, 3, 3679, 4789, 4),
(1486, 'NAICS', 205, 23, 1, 232, 2379, 3),
(1487, 'SIC', 4308, 20, 1, 3304, 3220, 3),
(1488, 'NAICS', 156, 2123, 3, 159, 212312, 5),
(1489, 'NAICS', 1920, 624, 2, 1938, 62431, 4),
(1490, 'NAICS', 1836, 6116, 3, 1840, 61162, 4),
(1491, 'SIC', 4311, 52, 1, 3873, 5714, 4),
(1492, 'SIC', 4308, 20, 1, 3244, 2875, 4),
(1493, 'NAICS', 180, 22, 1, 198, 2213, 3),
(1494, 'NAICS', 118, 1151, 3, 124, 115115, 5),
(1495, 'SIC', 3620, 4200, 2, 3622, 4212, 4),
(1496, 'NAICS', 1569, 53, 1, 1579, 53119, 4),
(1497, 'NAICS', 932, 4231, 3, 940, 42314, 4),
(1498, 'SIC', 3419, 3500, 2, 3450, 3559, 4),
(1499, 'NAICS', 1495, 5222, 3, 1499, 52222, 4),
(1500, 'SIC', 3419, 3500, 2, 3463, 3572, 4),
(1501, 'NAICS', 1480, 52, 1, 1502, 522292, 5),
(1502, 'NAICS', 1516, 52311, 4, 1515, 523110, 5),
(1503, 'NAICS', 2003, 72, 1, 2010, 72119, 4),
(1504, 'NAICS', 930, 42, 1, 1060, 42459, 4),
(1505, 'NAICS', 2037, 81, 1, 2092, 812332, 5),
(1506, 'SEC', 2791, 20, 1, 2271, 2300, 2),
(1507, 'SIC', 3961, 6320, 3, 3963, 6324, 4),
(1508, 'NAICS', 1944, 7111, 3, 1946, 71111, 4),
(1509, 'SIC', 4308, 20, 1, 2997, 2035, 4),
(1510, 'SEC', 2791, 20, 1, 2408, 3530, 3),
(1511, 'SIC', 3693, 4900, 2, 3713, 4970, 3),
(1512, 'SEC', 2654, 6030, 3, 2655, 6035, 4),
(1513, 'SIC', 2982, 2000, 2, 2996, 2034, 4),
(1514, 'NAICS', 132, 21, 1, 162, 21232, 4),
(1515, 'SIC', 4192, 8300, 2, 4197, 8350, 3),
(1516, 'NAICS', 1, 11, 1, 26, 111320, 5),
(1517, 'NAICS', 1518, 52312, 4, 1517, 523120, 5),
(1518, 'SIC', 3480, 3600, 2, 3495, 3639, 4),
(1519, 'SIC', 4017, 7200, 2, 4031, 7240, 3),
(1520, 'SIC', 4204, 8410, 3, 4205, 8412, 4),
(1521, 'SIC', 4305, 1, 1, 2798, 100, 2),
(1522, 'NAICS', 2005, 7211, 3, 2011, 721191, 5),
(1523, 'NAICS', 2150, 922, 2, 2151, 9221, 3),
(1524, 'NAICS', 1015, 424, 2, 1045, 42445, 4),
(1525, 'NAICS', 205, 23, 1, 239, 238120, 5),
(1526, 'NAICS', 1, 11, 1, 2, 111, 2),
(1527, 'NAICS', 1978, 71219, 4, 1977, 712190, 5),
(1528, 'SIC', 4308, 20, 1, 3516, 3676, 4),
(1529, 'NAICS', 2087, 81231, 4, 2086, 812310, 5),
(1530, 'SIC', 4309, 40, 1, 3697, 4922, 4),
(1531, 'SIC', 4308, 20, 1, 3383, 3433, 4),
(1532, 'SIC', 3258, 2990, 3, 3260, 2999, 4),
(1533, 'NAICS', 117, 115, 2, 124, 115115, 5),
(1534, 'SEC', 2791, 20, 1, 2423, 3569, 4),
(1535, 'NAICS', 1402, 51, 1, 1407, 511120, 5),
(1536, 'SIC', 4308, 20, 1, 3500, 3645, 4),
(1537, 'NAICS', 1624, 54, 1, 1653, 541370, 5),
(1538, 'NAICS', 1850, 62, 1, 1878, 621492, 5),
(1539, 'SEC', 2302, 2700, 2, 2316, 2771, 4),
(1540, 'NAICS', 941, 4232, 3, 944, 423220, 5),
(1541, 'SEC', 2568, 5000, 2, 2590, 5099, 4),
(1542, 'SIC', 4313, 70, 1, 4083, 7513, 4),
(1543, 'NAICS', 1418, 51121, 4, 1417, 511210, 5),
(1544, 'NAICS', 2037, 81, 1, 2084, 81222, 4),
(1545, 'SEC', 2791, 20, 1, 2291, 2590, 3),
(1546, 'SIC', 4256, 9200, 2, 4258, 9211, 4),
(1547, 'SIC', 4089, 7530, 3, 4090, 7532, 4),
(1548, 'NAICS', 52, 11199, 4, 54, 111992, 5),
(1549, 'NAICS', 117, 115, 2, 129, 1153, 3),
(1550, 'SIC', 2966, 1750, 3, 2967, 1751, 4),
(1551, 'SIC', 4313, 70, 1, 4191, 8299, 4),
(1552, 'SIC', 3375, 3420, 3, 3377, 3423, 4),
(1553, 'SIC', 4309, 40, 1, 3645, 4480, 3),
(1554, 'SEC', 2527, 4510, 3, 2529, 4513, 4),
(1555, 'SIC', 2914, 1380, 3, 2916, 1382, 4),
(1556, 'SIC', 3083, 2300, 2, 3120, 2395, 4),
(1557, 'NAICS', 1904, 623, 2, 1905, 6231, 3),
(1558, 'SIC', 3180, 2670, 3, 3183, 2673, 4),
(1559, 'SIC', 3869, 5700, 2, 3877, 5730, 3),
(1560, 'SIC', 4139, 7990, 3, 4145, 7999, 4),
(1561, 'NAICS', 1513, 523, 2, 1520, 52313, 4),
(1562, 'NAICS', 173, 2131, 3, 176, 213112, 5),
(1563, 'NAICS', 205, 23, 1, 266, 23833, 4),
(1564, 'SIC', 4308, 20, 1, 3154, 2517, 4),
(1565, 'SIC', 3854, 5600, 2, 3855, 5610, 3),
(1566, 'SIC', 4100, 7600, 2, 4107, 7640, 3),
(1567, 'SIC', 3190, 2700, 2, 3207, 2771, 4),
(1568, 'SEC', 2791, 20, 1, 2445, 3652, 4),
(1569, 'SEC', 2791, 20, 1, 2313, 2760, 3),
(1570, 'SIC', 4314, 90, 1, 4273, 9440, 3),
(1571, 'NAICS', 250, 23817, 4, 249, 238170, 5),
(1572, 'NAICS', 1813, 611, 2, 1816, 61111, 4),
(1573, 'SIC', 4314, 90, 1, 4289, 9630, 3),
(1574, 'SIC', 3115, 2390, 3, 3122, 2397, 4),
(1575, 'SIC', 3527, 3710, 3, 3528, 3711, 4),
(1576, 'SIC', 4308, 20, 1, 3159, 2530, 3),
(1577, 'SIC', 4314, 90, 1, 4303, 9990, 3),
(1578, 'SIC', 2982, 2000, 2, 2990, 2023, 4),
(1579, 'SIC', 3749, 5080, 3, 3752, 5084, 4),
(1580, 'NAICS', 1725, 56, 1, 1760, 56151, 4),
(1581, 'SEC', 2568, 5000, 2, 2570, 5013, 4),
(1582, 'SIC', 3083, 2300, 2, 3085, 2311, 4),
(1583, 'SIC', 3000, 2040, 3, 3003, 2044, 4),
(1584, 'SIC', 3797, 5190, 3, 3799, 5192, 4),
(1585, 'SEC', 2500, 3900, 2, 2502, 3911, 4),
(1586, 'NAICS', 1569, 53, 1, 1593, 53211, 4),
(1587, 'SEC', 2795, 60, 1, 2674, 6221, 4),
(1588, 'SIC', 4007, 7000, 2, 4009, 7011, 4),
(1589, 'SIC', 4313, 70, 1, 4059, 7352, 4),
(1590, 'SEC', 2552, 4900, 2, 2563, 4941, 4),
(1591, 'NAICS', 1942, 71, 1, 1986, 713210, 5),
(1592, 'SIC', 4305, 1, 1, 2839, 259, 4),
(1593, 'NAICS', 2153, 92211, 4, 2152, 922110, 5),
(1594, 'NAICS', 3, 1111, 3, 9, 11113, 4),
(1595, 'NAICS', 218, 237, 2, 227, 237210, 5),
(1596, 'NAICS', 23, 1113, 3, 26, 111320, 5),
(1597, 'NAICS', 1592, 5321, 3, 1593, 53211, 4),
(1598, 'NAICS', 2135, 92, 1, 2167, 9231, 3),
(1599, 'SEC', 2458, 3700, 2, 2473, 3751, 4),
(1600, 'SEC', 2793, 50, 1, 2592, 5110, 3),
(1601, 'NAICS', 3, 1111, 3, 6, 111120, 5),
(1602, 'SIC', 4311, 52, 1, 3869, 5700, 2),
(1603, 'SIC', 4308, 20, 1, 3484, 3620, 3),
(1604, 'SIC', 3033, 2090, 3, 3035, 2092, 4),
(1605, 'SIC', 2955, 1700, 2, 2956, 1710, 3),
(1606, 'SIC', 4308, 20, 1, 3178, 2656, 4),
(1607, 'SEC', 2319, 2800, 2, 2330, 2844, 4),
(1608, 'SIC', 3131, 2430, 3, 3134, 2435, 4),
(1609, 'SIC', 3148, 2500, 2, 3161, 2540, 3),
(1610, 'SEC', 2795, 60, 1, 2688, 6361, 4),
(1611, 'SIC', 4307, 15, 1, 2969, 1760, 3),
(1612, 'SIC', 2982, 2000, 2, 3022, 2075, 4),
(1613, 'NAICS', 1419, 512, 2, 1422, 51211, 4),
(1614, 'SEC', 2465, 3720, 3, 2466, 3721, 4),
(1615, 'SEC', 2753, 8000, 2, 2758, 8060, 3),
(1616, 'SIC', 3384, 3440, 3, 3388, 3444, 4),
(1617, 'NAICS', 52, 11199, 4, 53, 111991, 5),
(1618, 'NAICS', 1015, 424, 2, 1069, 424720, 5),
(1619, 'NAICS', 1568, 52599, 4, 1567, 525990, 5),
(1620, 'NAICS', 2151, 9221, 3, 2165, 92219, 4),
(1621, 'SEC', 2240, 2000, 2, 2256, 2086, 4),
(1622, 'SIC', 3419, 3500, 2, 3434, 3540, 3),
(1623, 'SIC', 3322, 3270, 3, 3323, 3271, 4),
(1624, 'SIC', 2940, 1520, 3, 2941, 1521, 4),
(1625, 'NAICS', 1942, 71, 1, 1982, 71311, 4),
(1626, 'SIC', 4305, 1, 1, 2821, 181, 4),
(1627, 'NAICS', 1431, 5122, 3, 1432, 512210, 5),
(1628, 'NAICS', 181, 221, 2, 201, 221320, 5),
(1629, 'NAICS', 1480, 52, 1, 1528, 52391, 4),
(1630, 'SEC', 2637, 5800, 2, 2638, 5810, 3),
(1631, 'SEC', 2403, 3500, 2, 2408, 3530, 3),
(1632, 'SIC', 3526, 3700, 2, 3542, 3750, 3),
(1633, 'SIC', 4158, 8050, 3, 4159, 8051, 4),
(1634, 'SEC', 2791, 20, 1, 2299, 2650, 3),
(1635, 'SIC', 3548, 3790, 3, 3550, 3795, 4),
(1636, 'SIC', 3480, 3600, 2, 3509, 3663, 4),
(1637, 'SEC', 2780, 8740, 3, 2782, 8742, 4),
(1638, 'NAICS', 56, 112, 2, 69, 112310, 5),
(1639, 'NAICS', 2003, 72, 1, 2029, 722410, 5),
(1640, 'SIC', 2875, 900, 2, 2877, 912, 4),
(1641, 'NAICS', 1843, 61169, 4, 1845, 611692, 5),
(1642, 'SIC', 3552, 3800, 2, 3558, 3823, 4),
(1643, 'SIC', 3762, 5100, 2, 3795, 5181, 4),
(1644, 'SIC', 2868, 800, 2, 2871, 830, 3),
(1645, 'NAICS', 1402, 51, 1, 1452, 517, 2),
(1646, 'NAICS', 1480, 52, 1, 1539, 524113, 5),
(1647, 'NAICS', 1741, 5614, 3, 1748, 561431, 5),
(1648, 'SEC', 2605, 5200, 2, 2609, 5271, 4),
(1649, 'NAICS', 2004, 721, 2, 2006, 721110, 5),
(1650, 'SEC', 2795, 60, 1, 2684, 6331, 4),
(1651, 'NAICS', 2135, 92, 1, 2202, 927110, 5),
(1652, 'SEC', 2774, 8700, 2, 2777, 8730, 3),
(1653, 'SIC', 3636, 4400, 2, 3646, 4481, 4),
(1654, 'SIC', 4309, 40, 1, 3676, 4780, 3),
(1655, 'SEC', 2791, 20, 1, 2344, 3011, 4),
(1656, 'SIC', 4311, 52, 1, 3816, 5310, 3),
(1657, 'NAICS', 1495, 5222, 3, 1498, 522220, 5),
(1658, 'SIC', 4312, 60, 1, 3983, 6517, 4),
(1659, 'NAICS', 1015, 424, 2, 1049, 42447, 4),
(1660, 'NAICS', 2028, 7224, 3, 2030, 72241, 4),
(1661, 'SIC', 4308, 20, 1, 3207, 2771, 4),
(1662, 'NAICS', 1, 11, 1, 83, 11242, 4),
(1663, 'SIC', 3419, 3500, 2, 3452, 3561, 4),
(1664, 'SIC', 4311, 52, 1, 3863, 5650, 3),
(1665, 'SEC', 2500, 3900, 2, 2508, 3949, 4),
(1666, 'NAICS', 930, 42, 1, 1070, 42472, 4),
(1667, 'SIC', 3083, 2300, 2, 3103, 2360, 3),
(1668, 'SIC', 4309, 40, 1, 3628, 4222, 4),
(1669, 'SIC', 3083, 2300, 2, 3117, 2392, 4),
(1670, 'SIC', 4230, 8730, 3, 4234, 8734, 4),
(1671, 'NAICS', 1968, 71151, 4, 1967, 711510, 5),
(1672, 'SIC', 4310, 50, 1, 3723, 5023, 4),
(1673, 'NAICS', 1706, 5419, 3, 1708, 54191, 4),
(1674, 'SEC', 2791, 20, 1, 2466, 3721, 4),
(1675, 'SIC', 3511, 3670, 3, 3518, 3678, 4),
(1676, 'SIC', 4314, 90, 1, 4300, 9720, 3),
(1677, 'SIC', 3124, 2400, 2, 3138, 2441, 4),
(1678, 'SIC', 4311, 52, 1, 3882, 5800, 2),
(1679, 'SIC', 4313, 70, 1, 4234, 8734, 4),
(1680, 'NAICS', 2, 111, 2, 36, 1114, 3),
(1681, 'NAICS', 205, 23, 1, 247, 238160, 5),
(1682, 'SEC', 2371, 3300, 2, 2377, 3334, 4),
(1683, 'SIC', 4313, 70, 1, 4162, 8060, 3),
(1684, 'NAICS', 2136, 921, 2, 2138, 921110, 5),
(1685, 'SEC', 2791, 20, 1, 2511, 3990, 3),
(1686, 'SIC', 4268, 9400, 2, 4273, 9440, 3),
(1687, 'SIC', 4313, 70, 1, 4156, 8043, 4),
(1688, 'NAICS', 1726, 561, 2, 1734, 56131, 4),
(1689, 'NAICS', 109, 1141, 3, 112, 114112, 5),
(1690, 'SIC', 3282, 3100, 2, 3291, 3149, 4),
(1691, 'SIC', 3715, 5000, 2, 3733, 5046, 4),
(1692, 'SIC', 4223, 8700, 2, 4225, 8711, 4),
(1693, 'NAICS', 1706, 5419, 3, 1715, 54194, 4),
(1694, 'NAICS', 1942, 71, 1, 1951, 711190, 5),
(1695, 'NAICS', 1626, 5411, 3, 1630, 54112, 4),
(1696, 'NAICS', 1, 11, 1, 126, 1152, 3),
(1697, 'NAICS', 1920, 624, 2, 1929, 624210, 5),
(1698, 'NAICS', 2038, 811, 2, 2057, 811219, 5),
(1699, 'SEC', 2791, 20, 1, 2411, 3533, 4),
(1700, 'SIC', 4308, 20, 1, 3406, 3483, 4),
(1701, 'SEC', 2237, 1700, 2, 2238, 1730, 3),
(1702, 'SEC', 2349, 3080, 3, 2350, 3081, 4),
(1703, 'SIC', 2825, 200, 2, 2836, 252, 4),
(1704, 'SEC', 2791, 20, 1, 2504, 3931, 4),
(1705, 'NAICS', 2189, 9261, 3, 2195, 92613, 4),
(1706, 'SEC', 2794, 52, 1, 2631, 5710, 3),
(1707, 'SIC', 4308, 20, 1, 3571, 3851, 4),
(1708, 'SIC', 4018, 7210, 3, 4022, 7215, 4),
(1709, 'NAICS', 931, 423, 2, 933, 423110, 5),
(1710, 'NAICS', 132, 21, 1, 142, 212112, 5),
(1711, 'NAICS', 1, 11, 1, 88, 112519, 5),
(1712, 'NAICS', 1882, 62151, 4, 1884, 621512, 5),
(1713, 'SIC', 3762, 5100, 2, 3786, 5154, 4),
(1714, 'SIC', 3371, 3400, 2, 3391, 3449, 4),
(1715, 'SIC', 3886, 5900, 2, 3890, 5921, 4),
(1716, 'SEC', 2615, 5390, 3, 2616, 5399, 4),
(1717, 'NAICS', 1942, 71, 1, 1948, 71112, 4),
(1718, 'SIC', 4308, 20, 1, 3389, 3446, 4),
(1719, 'NAICS', 2135, 92, 1, 2143, 92113, 4),
(1720, 'SEC', 2791, 20, 1, 2279, 2430, 3),
(1721, 'NAICS', 1942, 71, 1, 1995, 713930, 5),
(1722, 'NAICS', 2071, 812, 2, 2089, 81232, 4),
(1723, 'NAICS', 2037, 81, 1, 2071, 812, 2),
(1724, 'SIC', 4313, 70, 1, 4245, 8990, 3),
(1725, 'NAICS', 930, 42, 1, 1084, 42494, 4),
(1726, 'NAICS', 2038, 811, 2, 2052, 8112, 3),
(1727, 'NAICS', 150, 21223, 4, 152, 212234, 5),
(1728, 'NAICS', 1726, 561, 2, 1747, 56143, 4),
(1729, 'SEC', 2791, 20, 1, 2336, 2891, 4),
(1730, 'SIC', 3252, 2900, 2, 3254, 2911, 4),
(1731, 'NAICS', 2, 111, 2, 23, 1113, 3),
(1732, 'SIC', 4312, 60, 1, 3993, 6710, 3),
(1733, 'NAICS', 195, 2212, 3, 197, 22121, 4),
(1734, 'SIC', 2875, 900, 2, 2879, 919, 4),
(1735, 'SEC', 2523, 4400, 2, 2524, 4410, 3),
(1736, 'SIC', 4312, 60, 1, 3943, 6153, 4),
(1737, 'SIC', 3012, 2060, 3, 3014, 2062, 4),
(1738, 'NAICS', 2209, 92812, 4, 2208, 928120, 5),
(1739, 'SIC', 4309, 40, 1, 3626, 4220, 3),
(1740, 'SIC', 4313, 70, 1, 4161, 8059, 4),
(1741, 'NAICS', 930, 42, 1, 972, 42351, 4),
(1742, 'SIC', 3174, 2650, 3, 3175, 2652, 4),
(1743, 'SIC', 3886, 5900, 2, 3905, 5962, 4),
(1744, 'SIC', 4313, 70, 1, 4220, 8661, 4),
(1745, 'SIC', 4310, 50, 1, 3731, 5044, 4),
(1746, 'SIC', 4310, 50, 1, 3761, 5099, 4),
(1747, 'SIC', 4308, 20, 1, 3238, 2861, 4),
(1748, 'SEC', 2791, 20, 1, 2459, 3710, 3),
(1749, 'NAICS', 2062, 81141, 4, 2063, 811411, 5),
(1750, 'NAICS', 1726, 561, 2, 1746, 561422, 5),
(1751, 'SIC', 3419, 3500, 2, 3420, 3510, 3),
(1752, 'NAICS', 1912, 62322, 4, 1911, 623220, 5),
(1753, 'NAICS', 2071, 812, 2, 2100, 81293, 4),
(1754, 'SEC', 2771, 8350, 3, 2772, 8351, 4),
(1755, 'SIC', 2868, 800, 2, 2874, 851, 4),
(1756, 'NAICS', 1470, 519, 2, 1475, 51912, 4),
(1757, 'NAICS', 2135, 92, 1, 2141, 92112, 4),
(1758, 'SIC', 3842, 5530, 3, 3843, 5531, 4),
(1759, 'SIC', 4040, 7300, 2, 4074, 7379, 4),
(1760, 'SEC', 2795, 60, 1, 4324, 6190, 3),
(1761, 'SIC', 3033, 2090, 3, 3034, 2091, 4),
(1762, 'SIC', 4312, 60, 1, 4004, 6794, 4),
(1763, 'NAICS', 1456, 5172, 3, 1458, 51721, 4),
(1764, 'SIC', 4308, 20, 1, 3498, 3643, 4),
(1765, 'SEC', 2545, 4830, 3, 2546, 4832, 4),
(1766, 'SIC', 4312, 60, 1, 3965, 6331, 4),
(1767, 'SIC', 2798, 100, 2, 2799, 110, 3),
(1768, 'SIC', 4213, 8630, 3, 4214, 8631, 4),
(1769, 'NAICS', 1881, 6215, 3, 1884, 621512, 5),
(1770, 'NAICS', 156, 2123, 3, 165, 212324, 5),
(1771, 'SIC', 4308, 20, 1, 3000, 2040, 3),
(1772, 'SIC', 4309, 40, 1, 3605, 4100, 2),
(1773, 'SIC', 3715, 5000, 2, 3724, 5030, 3),
(1774, 'NAICS', 1625, 541, 2, 1653, 541370, 5),
(1775, 'NAICS', 2150, 922, 2, 2158, 922140, 5),
(1776, 'NAICS', 2151, 9221, 3, 2157, 92213, 4),
(1777, 'SIC', 2982, 2000, 2, 3020, 2070, 3),
(1778, 'NAICS', 180, 22, 1, 200, 22131, 4),
(1779, 'SEC', 2391, 3440, 3, 2395, 3448, 4),
(1780, 'NAICS', 134, 2111, 3, 136, 211111, 5),
(1781, 'NAICS', 181, 221, 2, 182, 2211, 3),
(1782, 'NAICS', 2038, 811, 2, 2051, 811198, 5),
(1783, 'SIC', 3304, 3220, 3, 3306, 3229, 4),
(1784, 'NAICS', 2090, 81233, 4, 2091, 812331, 5),
(1785, 'SIC', 3992, 6700, 2, 3998, 6726, 4),
(1786, 'NAICS', 205, 23, 1, 222, 237120, 5),
(1787, 'SEC', 2796, 70, 1, 2760, 8070, 3),
(1788, 'NAICS', 2038, 811, 2, 2062, 81141, 4),
(1789, 'NAICS', 1, 11, 1, 74, 11233, 4),
(1790, 'NAICS', 1942, 71, 1, 1969, 712, 2),
(1791, 'NAICS', 2093, 8129, 3, 2096, 81292, 4),
(1792, 'SEC', 2319, 2800, 2, 2326, 2835, 4),
(1793, 'SEC', 2680, 6320, 3, 2682, 6324, 4),
(1794, 'NAICS', 40, 11142, 4, 42, 111422, 5),
(1795, 'NAICS', 1620, 533, 2, 1621, 5331, 3),
(1796, 'SIC', 3148, 2500, 2, 3163, 2542, 4),
(1797, 'SEC', 2738, 7800, 2, 2743, 7822, 4),
(1798, 'SIC', 4314, 90, 1, 4248, 9110, 3),
(1799, 'NAICS', 1942, 71, 1, 1994, 71392, 4),
(1800, 'SIC', 4311, 52, 1, 3825, 5420, 3),
(1801, 'SIC', 4313, 70, 1, 4014, 7033, 4),
(1802, 'NAICS', 1928, 6242, 3, 1934, 624230, 5),
(1803, 'NAICS', 1480, 52, 1, 1534, 523991, 5),
(1804, 'SEC', 2292, 2600, 2, 2299, 2650, 3),
(1805, 'SEC', 2513, 4010, 3, 2514, 4011, 4),
(1806, 'NAICS', 1990, 7139, 3, 1997, 713940, 5),
(1807, 'SIC', 2945, 1540, 3, 2946, 1541, 4),
(1808, 'SIC', 4308, 20, 1, 3279, 3087, 4),
(1809, 'SIC', 4308, 20, 1, 3518, 3678, 4),
(1810, 'SIC', 3616, 4150, 3, 3617, 4151, 4),
(1811, 'SEC', 2269, 2270, 3, 2270, 2273, 4),
(1812, 'SIC', 4308, 20, 1, 3245, 2879, 4),
(1813, 'NAICS', 273, 2389, 3, 276, 238990, 5),
(1814, 'NAICS', 37, 11141, 4, 39, 111419, 5),
(1815, 'NAICS', 1485, 522, 2, 1487, 522110, 5),
(1816, 'NAICS', 1621, 5331, 3, 1622, 533110, 5),
(1817, 'SIC', 3059, 2250, 3, 3060, 2251, 4),
(1818, 'SIC', 4308, 20, 1, 3197, 2732, 4),
(1819, 'SIC', 4113, 7800, 2, 4123, 7840, 3),
(1820, 'SIC', 4308, 20, 1, 3415, 3496, 4),
(1821, 'SIC', 3419, 3500, 2, 3421, 3511, 4),
(1822, 'SIC', 3261, 3000, 2, 3278, 3086, 4),
(1823, 'NAICS', 1725, 56, 1, 1793, 5621, 3),
(1824, 'SEC', 2792, 40, 1, 2559, 4930, 3),
(1825, 'SIC', 4146, 8000, 2, 4171, 8090, 3),
(1826, 'SEC', 2543, 4820, 3, 2544, 4822, 4),
(1827, 'SIC', 4012, 7030, 3, 4013, 7032, 4),
(1828, 'NAICS', 1969, 712, 2, 1973, 712120, 5),
(1829, 'SIC', 3124, 2400, 2, 3136, 2439, 4),
(1830, 'SIC', 4308, 20, 1, 3016, 2064, 4),
(1831, 'SIC', 4308, 20, 1, 3526, 3700, 2),
(1832, 'SIC', 4235, 8740, 3, 4237, 8742, 4),
(1833, 'SIC', 4309, 40, 1, 3703, 4932, 4),
(1834, 'NAICS', 1428, 51219, 4, 1430, 512199, 5),
(1835, 'NAICS', 180, 22, 1, 187, 221114, 5),
(1836, 'NAICS', 930, 42, 1, 968, 423490, 5),
(1837, 'SIC', 4309, 40, 1, 3608, 4119, 4),
(1838, 'NAICS', 58, 11211, 4, 60, 112112, 5),
(1839, 'SEC', 2403, 3500, 2, 2411, 3533, 4),
(1840, 'NAICS', 1554, 525, 2, 1559, 52512, 4),
(1841, 'SEC', 2512, 4000, 2, 2514, 4011, 4),
(1842, 'SIC', 3636, 4400, 2, 3639, 4420, 3),
(1843, 'SIC', 4018, 7210, 3, 4026, 7219, 4),
(1844, 'NAICS', 1626, 5411, 3, 1628, 54111, 4),
(1845, 'NAICS', 2037, 81, 1, 2111, 813219, 5),
(1846, 'NAICS', 172, 213, 2, 173, 2131, 3),
(1847, 'SIC', 2825, 200, 2, 2846, 291, 4),
(1848, 'SIC', 4308, 20, 1, 3497, 3641, 4),
(1849, 'SIC', 3484, 3620, 3, 3486, 3624, 4),
(1850, 'SEC', 2579, 5060, 3, 2580, 5063, 4),
(1851, 'NAICS', 1402, 51, 1, 1440, 512290, 5),
(1852, 'SIC', 4308, 20, 1, 3548, 3790, 3),
(1853, 'NAICS', 205, 23, 1, 237, 238110, 5),
(1854, 'SIC', 3337, 3300, 2, 3355, 3350, 3),
(1855, 'SIC', 3667, 4700, 2, 3672, 4730, 3),
(1856, 'NAICS', 1942, 71, 1, 1976, 71213, 4),
(1857, 'NAICS', 2037, 81, 1, 2053, 81121, 4),
(1858, 'SEC', 2548, 4840, 3, 2549, 4841, 4),
(1859, 'NAICS', 2176, 924, 2, 2179, 92411, 4),
(1860, 'SEC', 2791, 20, 1, 2246, 2024, 4),
(1861, 'SIC', 4308, 20, 1, 3469, 3581, 4),
(1862, 'NAICS', 965, 42345, 4, 964, 423450, 5),
(1863, 'SEC', 2476, 3800, 2, 2484, 3825, 4),
(1864, 'SIC', 3480, 3600, 2, 3494, 3635, 4),
(1865, 'SIC', 3763, 5110, 3, 3766, 5113, 4),
(1866, 'SIC', 4308, 20, 1, 3331, 3291, 4),
(1867, 'NAICS', 1537, 5241, 3, 1545, 524130, 5),
(1868, 'NAICS', 206, 236, 2, 215, 23621, 4),
(1869, 'SIC', 3480, 3600, 2, 3512, 3671, 4),
(1870, 'SEC', 2372, 3310, 3, 2374, 3317, 4),
(1871, 'NAICS', 79, 1124, 3, 83, 11242, 4),
(1872, 'SIC', 4308, 20, 1, 3543, 3751, 4),
(1873, 'SIC', 4018, 7210, 3, 4024, 7217, 4),
(1874, 'NAICS', 1015, 424, 2, 1068, 42471, 4),
(1875, 'NAICS', 236, 2381, 3, 245, 238150, 5),
(1876, 'SEC', 2725, 7370, 3, 2726, 7371, 4),
(1877, 'SIC', 2955, 1700, 2, 2960, 1730, 3),
(1878, 'SIC', 4310, 50, 1, 3770, 5131, 4),
(1879, 'NAICS', 1015, 424, 2, 1027, 424310, 5),
(1880, 'SIC', 2949, 1610, 3, 2950, 1611, 4),
(1881, 'SIC', 4065, 7370, 3, 4072, 7377, 4),
(1882, 'NAICS', 1, 11, 1, 84, 1125, 3),
(1883, 'NAICS', 1554, 525, 2, 1563, 525910, 5),
(1884, 'NAICS', 1942, 71, 1, 1950, 71113, 4),
(1885, 'SEC', 2792, 40, 1, 2548, 4840, 3),
(1886, 'SEC', 2793, 50, 1, 2588, 5090, 3),
(1887, 'SIC', 4306, 10, 1, 2901, 1200, 2),
(1888, 'SIC', 3124, 2400, 2, 3144, 2490, 3),
(1889, 'SIC', 4040, 7300, 2, 4066, 7371, 4),
(1890, 'SEC', 2795, 60, 1, 2668, 6162, 4),
(1891, 'SIC', 3419, 3500, 2, 3466, 3578, 4),
(1892, 'NAICS', 1420, 5121, 3, 1422, 51211, 4),
(1893, 'SIC', 4312, 60, 1, 3923, 6022, 4),
(1894, 'NAICS', 1741, 5614, 3, 1745, 561421, 5),
(1895, 'NAICS', 1904, 623, 2, 1913, 6233, 3),
(1896, 'SIC', 3301, 3200, 2, 3316, 3260, 3),
(1897, 'NAICS', 1851, 621, 2, 1861, 62131, 4),
(1898, 'SIC', 2805, 130, 3, 2808, 133, 4),
(1899, 'NAICS', 1725, 56, 1, 1759, 561510, 5),
(1900, 'SEC', 2288, 2530, 3, 2289, 2531, 4),
(1901, 'NAICS', 930, 42, 1, 973, 423520, 5),
(1902, 'SIC', 2955, 1700, 2, 2965, 1743, 4),
(1903, 'SIC', 4125, 7900, 2, 4144, 7997, 4),
(1904, 'NAICS', 1, 11, 1, 61, 112120, 5),
(1905, 'NAICS', 1402, 51, 1, 1423, 512120, 5),
(1906, 'SEC', 2792, 40, 1, 2545, 4830, 3),
(1907, 'NAICS', 140, 21211, 4, 141, 212111, 5),
(1908, 'SIC', 4306, 10, 1, 2914, 1380, 3),
(1909, 'SIC', 3190, 2700, 2, 3197, 2732, 4),
(1910, 'SIC', 4308, 20, 1, 3442, 3548, 4),
(1911, 'NAICS', 182, 2211, 3, 192, 22112, 4),
(1912, 'NAICS', 1626, 5411, 3, 1627, 541110, 5),
(1913, 'SIC', 4105, 7630, 3, 4106, 7631, 4),
(1914, 'NAICS', 2120, 8139, 3, 2127, 813940, 5),
(1915, 'SEC', 2794, 52, 1, 2643, 5940, 3),
(1916, 'SEC', 2418, 3560, 3, 2420, 3562, 4),
(1917, 'SIC', 4235, 8740, 3, 4239, 8744, 4),
(1918, 'SIC', 2876, 910, 3, 2879, 919, 4),
(1919, 'NAICS', 931, 423, 2, 944, 423220, 5),
(1920, 'SIC', 4308, 20, 1, 3506, 3652, 4),
(1921, 'SIC', 4310, 50, 1, 3774, 5140, 3),
(1922, 'SIC', 3992, 6700, 2, 3999, 6730, 3),
(1923, 'SIC', 3989, 6550, 3, 3991, 6553, 4),
(1924, 'SEC', 2479, 3820, 3, 2483, 3824, 4),
(1925, 'NAICS', 1927, 62419, 4, 1926, 624190, 5),
(1926, 'NAICS', 2071, 812, 2, 2077, 81219, 4),
(1927, 'NAICS', 1480, 52, 1, 1550, 52429, 4),
(1928, 'SEC', 2791, 20, 1, 2507, 3944, 4),
(1929, 'SIC', 3762, 5100, 2, 3766, 5113, 4),
(1930, 'SEC', 2795, 60, 1, 2650, 6020, 3),
(1931, 'NAICS', 1015, 424, 2, 1066, 4247, 3),
(1932, 'SEC', 2796, 70, 1, 2721, 7359, 4),
(1933, 'SEC', 2748, 7900, 2, 2749, 7940, 3),
(1934, 'NAICS', 1571, 5311, 3, 1576, 531130, 5),
(1935, 'SIC', 3992, 6700, 2, 3994, 6712, 4),
(1936, 'SIC', 3762, 5100, 2, 3802, 5198, 4),
(1937, 'SIC', 4308, 20, 1, 3574, 3870, 3),
(1938, 'NAICS', 1591, 532, 2, 1600, 53221, 4),
(1939, 'NAICS', 1766, 5616, 3, 1772, 561621, 5),
(1940, 'NAICS', 1774, 5617, 3, 1776, 56171, 4),
(1941, 'SIC', 4307, 15, 1, 2966, 1750, 3),
(1942, 'SIC', 4308, 20, 1, 3527, 3710, 3),
(1943, 'NAICS', 1023, 4242, 3, 1024, 424210, 5),
(1944, 'SIC', 4306, 10, 1, 2920, 1411, 4),
(1945, 'NAICS', 2003, 72, 1, 2024, 722320, 5),
(1946, 'SEC', 2355, 3200, 2, 2364, 3250, 3),
(1947, 'SIC', 3552, 3800, 2, 3565, 3841, 4),
(1948, 'NAICS', 1774, 5617, 3, 1777, 561720, 5),
(1949, 'SIC', 2847, 700, 2, 2848, 710, 3),
(1950, 'NAICS', 1076, 4249, 3, 1077, 424910, 5),
(1951, 'SIC', 2955, 1700, 2, 2970, 1761, 4),
(1952, 'SIC', 3705, 4940, 3, 3706, 4941, 4),
(1953, 'SIC', 4307, 15, 1, 2959, 1721, 4),
(1954, 'NAICS', 1402, 51, 1, 1470, 519, 2),
(1955, 'NAICS', 1850, 62, 1, 1880, 621498, 5),
(1956, 'SEC', 2796, 70, 1, 2711, 7011, 4),
(1957, 'SIC', 2982, 2000, 2, 3002, 2043, 4),
(1958, 'NAICS', 1931, 62422, 4, 1933, 624229, 5),
(1959, 'NAICS', 1850, 62, 1, 1888, 6219, 3),
(1960, 'NAICS', 2003, 72, 1, 2026, 722330, 5),
(1961, 'SEC', 2476, 3800, 2, 2493, 3845, 4),
(1962, 'SIC', 4309, 40, 1, 3690, 4841, 4),
(1963, 'SIC', 4081, 7500, 2, 4090, 7532, 4),
(1964, 'NAICS', 931, 423, 2, 934, 42311, 4),
(1965, 'SIC', 4311, 52, 1, 3853, 5599, 4),
(1966, 'NAICS', 1672, 5416, 3, 1677, 541614, 5),
(1967, 'SEC', 2568, 5000, 2, 2578, 5051, 4),
(1968, 'SIC', 3371, 3400, 2, 3383, 3433, 4),
(1969, 'SIC', 3645, 4480, 3, 3646, 4481, 4),
(1970, 'SIC', 3419, 3500, 2, 3448, 3555, 4),
(1971, 'NAICS', 205, 23, 1, 220, 237110, 5),
(1972, 'NAICS', 1624, 54, 1, 1669, 541512, 5),
(1973, 'NAICS', 2020, 722, 2, 2021, 7223, 3),
(1974, 'SIC', 4308, 20, 1, 3451, 3560, 3),
(1975, 'SIC', 4125, 7900, 2, 4135, 7948, 4),
(1976, 'SIC', 3724, 5030, 3, 3726, 5032, 4),
(1977, 'NAICS', 2, 111, 2, 7, 11112, 4),
(1978, 'NAICS', 1908, 6232, 3, 1909, 623210, 5),
(1979, 'SIC', 3301, 3200, 2, 3329, 3281, 4),
(1980, 'SIC', 4311, 52, 1, 3862, 5641, 4),
(1981, 'NAICS', 182, 2211, 3, 190, 221117, 5),
(1982, 'SEC', 2796, 70, 1, 2752, 7997, 4),
(1983, 'SEC', 2539, 4800, 2, 2550, 4890, 3),
(1984, 'SIC', 4244, 8900, 2, 4245, 8990, 3),
(1985, 'NAICS', 1613, 53241, 4, 1614, 532411, 5),
(1986, 'SIC', 4100, 7600, 2, 4112, 7699, 4),
(1987, 'NAICS', 930, 42, 1, 1057, 424520, 5),
(1988, 'SIC', 4040, 7300, 2, 4047, 7322, 4),
(1989, 'NAICS', 930, 42, 1, 1053, 42449, 4),
(1990, 'NAICS', 1402, 51, 1, 1438, 512240, 5),
(1991, 'NAICS', 1706, 5419, 3, 1712, 541930, 5),
(1992, 'SEC', 2791, 20, 1, 2401, 3480, 3),
(1993, 'SIC', 4311, 52, 1, 3847, 5551, 4),
(1994, 'NAICS', 2135, 92, 1, 2209, 92812, 4),
(1995, 'SIC', 3000, 2040, 3, 3001, 2041, 4),
(1996, 'SIC', 3848, 5560, 3, 3849, 5561, 4),
(1997, 'SIC', 3576, 3900, 2, 3581, 3930, 3),
(1998, 'NAICS', 181, 221, 2, 186, 221113, 5),
(1999, 'SIC', 3762, 5100, 2, 3764, 5111, 4),
(2000, 'SIC', 3989, 6550, 3, 3990, 6552, 4),
(2001, 'NAICS', 235, 238, 2, 269, 238350, 5),
(2002, 'NAICS', 1930, 62421, 4, 1929, 624210, 5),
(2003, 'SIC', 3050, 2200, 2, 3060, 2251, 4),
(2004, 'SIC', 3167, 2600, 2, 3177, 2655, 4),
(2005, 'SEC', 2792, 40, 1, 4318, 4991, 3),
(2006, 'SEC', 2780, 8740, 3, 2781, 8741, 4),
(2007, 'SEC', 2568, 5000, 2, 2569, 5010, 3),
(2008, 'NAICS', 930, 42, 1, 1058, 42452, 4),
(2009, 'SEC', 2793, 50, 1, 2594, 5122, 4),
(2010, 'SIC', 4089, 7530, 3, 4091, 7533, 4),
(2011, 'SEC', 2605, 5200, 2, 2607, 5211, 4),
(2012, 'NAICS', 56, 112, 2, 72, 11232, 4),
(2013, 'NAICS', 2037, 81, 1, 2097, 812921, 5),
(2014, 'SIC', 4311, 52, 1, 3812, 5261, 4),
(2015, 'SEC', 2791, 20, 1, 2375, 3320, 3),
(2016, 'NAICS', 1725, 56, 1, 1784, 56179, 4),
(2017, 'SIC', 3362, 3360, 3, 3367, 3369, 4),
(2018, 'SIC', 3167, 2600, 2, 3169, 2611, 4),
(2019, 'NAICS', 56, 112, 2, 89, 1129, 3),
(2020, 'NAICS', 1640, 5413, 3, 1641, 541310, 5),
(2021, 'SEC', 2476, 3800, 2, 2488, 3840, 3),
(2022, 'SIC', 3261, 3000, 2, 3280, 3088, 4),
(2023, 'NAICS', 1480, 52, 1, 1557, 52511, 4),
(2024, 'SIC', 2850, 720, 3, 2853, 723, 4),
(2025, 'SIC', 4308, 20, 1, 3584, 3942, 4),
(2026, 'SIC', 4310, 50, 1, 3751, 5083, 4),
(2027, 'NAICS', 931, 423, 2, 950, 42332, 4),
(2028, 'NAICS', 1499, 52222, 4, 1498, 522220, 5),
(2029, 'NAICS', 2, 111, 2, 42, 111422, 5),
(2030, 'NAICS', 1513, 523, 2, 1532, 52393, 4),
(2031, 'NAICS', 1843, 61169, 4, 1846, 611699, 5),
(2032, 'SEC', 2552, 4900, 2, 2557, 4923, 4),
(2033, 'SIC', 3451, 3560, 3, 3460, 3569, 4),
(2034, 'SIC', 4313, 70, 1, 4130, 7929, 4),
(2035, 'NAICS', 1689, 5418, 3, 1690, 541810, 5),
(2036, 'SEC', 2791, 20, 1, 2302, 2700, 2),
(2037, 'SIC', 3816, 5310, 3, 3817, 5311, 4),
(2038, 'NAICS', 1942, 71, 1, 2002, 71399, 4),
(2039, 'NAICS', 1, 11, 1, 60, 112112, 5),
(2040, 'NAICS', 2037, 81, 1, 2123, 813920, 5),
(2041, 'SIC', 4017, 7200, 2, 4022, 7215, 4),
(2042, 'NAICS', 931, 423, 2, 960, 423430, 5),
(2043, 'SIC', 4312, 60, 1, 3929, 6061, 4),
(2044, 'NAICS', 129, 1153, 3, 130, 115310, 5),
(2045, 'SIC', 3707, 4950, 3, 3709, 4953, 4),
(2046, 'NAICS', 1920, 624, 2, 1930, 62421, 4),
(2047, 'SIC', 3337, 3300, 2, 3359, 3355, 4),
(2048, 'NAICS', 2167, 9231, 3, 2168, 923110, 5),
(2049, 'NAICS', 1, 11, 1, 99, 1131, 3),
(2050, 'SEC', 2302, 2700, 2, 2307, 2730, 3),
(2051, 'SIC', 3921, 6020, 3, 3924, 6029, 4),
(2052, 'SEC', 2791, 20, 1, 2481, 3822, 4),
(2053, 'SIC', 4089, 7530, 3, 4095, 7538, 4),
(2054, 'NAICS', 2, 111, 2, 43, 1119, 3),
(2055, 'NAICS', 181, 221, 2, 193, 221121, 5),
(2056, 'SIC', 3948, 6200, 2, 3951, 6220, 3),
(2057, 'SIC', 4128, 7920, 3, 4129, 7922, 4),
(2058, 'SIC', 4308, 20, 1, 3298, 3172, 4),
(2059, 'SIC', 3337, 3300, 2, 3350, 3331, 4),
(2060, 'SEC', 2760, 8070, 3, 2761, 8071, 4),
(2061, 'SIC', 3214, 2800, 2, 3220, 2820, 3),
(2062, 'SIC', 3763, 5110, 3, 3764, 5111, 4),
(2063, 'SIC', 4310, 50, 1, 3747, 5075, 4),
(2064, 'NAICS', 1850, 62, 1, 1937, 624310, 5),
(2065, 'SIC', 2825, 200, 2, 2832, 240, 3),
(2066, 'NAICS', 1403, 511, 2, 1412, 51114, 4),
(2067, 'SEC', 2791, 20, 1, 2398, 3452, 4),
(2068, 'SEC', 2792, 40, 1, 2561, 4932, 4),
(2069, 'NAICS', 95, 11293, 4, 94, 112930, 5),
(2070, 'SEC', 2319, 2800, 2, 2329, 2842, 4),
(2071, 'NAICS', 43, 1119, 3, 55, 111998, 5),
(2072, 'NAICS', 1943, 711, 2, 1944, 7111, 3),
(2073, 'SIC', 2956, 1710, 3, 2957, 1711, 4),
(2074, 'NAICS', 213, 2362, 3, 217, 23622, 4),
(2075, 'SIC', 3576, 3900, 2, 3594, 3965, 4),
(2076, 'NAICS', 1, 11, 1, 22, 111219, 5),
(2077, 'NAICS', 1086, 42495, 4, 1085, 424950, 5),
(2078, 'SIC', 4305, 1, 1, 2870, 811, 4),
(2079, 'SIC', 4308, 20, 1, 3473, 3589, 4),
(2080, 'NAICS', 173, 2131, 3, 177, 213113, 5),
(2081, 'SEC', 2371, 3300, 2, 2383, 3390, 3),
(2082, 'SIC', 4311, 52, 1, 3912, 5992, 4),
(2083, 'NAICS', 119, 11511, 4, 122, 115113, 5),
(2084, 'SEC', 2283, 2500, 2, 2284, 2510, 3),
(2085, 'SIC', 3958, 6300, 2, 3966, 6350, 3),
(2086, 'SIC', 2861, 760, 3, 2862, 761, 4),
(2087, 'NAICS', 1733, 5613, 3, 1734, 56131, 4),
(2088, 'NAICS', 2062, 81141, 4, 2064, 811412, 5),
(2089, 'NAICS', 1514, 5231, 3, 1518, 52312, 4),
(2090, 'NAICS', 1625, 541, 2, 1665, 54149, 4),
(2091, 'NAICS', 1944, 7111, 3, 1947, 711120, 5),
(2092, 'SEC', 2791, 20, 1, 2286, 2520, 3),
(2093, 'SIC', 3282, 3100, 2, 3293, 3151, 4),
(2094, 'SIC', 3827, 5430, 3, 3828, 5431, 4),
(2095, 'NAICS', 144, 2122, 3, 153, 21229, 4),
(2096, 'NAICS', 1513, 523, 2, 1531, 523930, 5),
(2097, 'SEC', 2319, 2800, 2, 2323, 2830, 3),
(2098, 'SIC', 4313, 70, 1, 4148, 8011, 4),
(2099, 'SIC', 4113, 7800, 2, 4114, 7810, 3),
(2100, 'SEC', 2313, 2760, 3, 2314, 2761, 4),
(2101, 'SIC', 4314, 90, 1, 4297, 9700, 2),
(2102, 'SIC', 3214, 2800, 2, 3236, 2851, 4),
(2103, 'NAICS', 2166, 923, 2, 2174, 923140, 5),
(2104, 'SEC', 2791, 20, 1, 2416, 3555, 4),
(2105, 'SIC', 4308, 20, 1, 3568, 3844, 4),
(2106, 'SIC', 4313, 70, 1, 4049, 7330, 3),
(2107, 'SIC', 3715, 5000, 2, 3759, 5093, 4),
(2108, 'SIC', 3886, 5900, 2, 3901, 5948, 4),
(2109, 'SEC', 2262, 2200, 2, 2270, 2273, 4),
(2110, 'NAICS', 1920, 624, 2, 1941, 62441, 4),
(2111, 'NAICS', 2128, 81394, 4, 2127, 813940, 5),
(2112, 'SEC', 2307, 2730, 3, 2309, 2732, 4),
(2113, 'SEC', 2792, 40, 1, 2528, 4512, 4),
(2114, 'NAICS', 1480, 52, 1, 1521, 523140, 5),
(2115, 'SEC', 2355, 3200, 2, 2358, 3220, 3),
(2116, 'SIC', 3893, 5940, 3, 3896, 5943, 4),
(2117, 'SIC', 4313, 70, 1, 4217, 8650, 3),
(2118, 'NAICS', 1850, 62, 1, 1884, 621512, 5),
(2119, 'SIC', 3676, 4780, 3, 3678, 4785, 4),
(2120, 'SEC', 2792, 40, 1, 2562, 4940, 3),
(2121, 'SEC', 2677, 6300, 2, 2681, 6321, 4),
(2122, 'SIC', 4311, 52, 1, 3915, 5995, 4),
(2123, 'SIC', 4313, 70, 1, 4104, 7629, 4),
(2124, 'NAICS', 1495, 5222, 3, 1503, 522293, 5),
(2125, 'NAICS', 1836, 6116, 3, 1843, 61169, 4),
(2126, 'SIC', 4017, 7200, 2, 4026, 7219, 4),
(2127, 'SIC', 4313, 70, 1, 4147, 8010, 3),
(2128, 'SEC', 2795, 60, 1, 2686, 6351, 4),
(2129, 'SEC', 2795, 60, 1, 2692, 6410, 3),
(2130, 'NAICS', 930, 42, 1, 948, 42331, 4),
(2131, 'SIC', 3301, 3200, 2, 3324, 3272, 4),
(2132, 'SIC', 4310, 50, 1, 3765, 5112, 4),
(2133, 'NAICS', 1741, 5614, 3, 1755, 561491, 5),
(2134, 'SEC', 2791, 20, 1, 2388, 3420, 3),
(2135, 'NAICS', 1762, 56152, 4, 1761, 561520, 5),
(2136, 'SIC', 3601, 4000, 2, 3603, 4011, 4),
(2137, 'SIC', 4310, 50, 1, 3783, 5149, 4),
(2138, 'SIC', 3426, 3530, 3, 3431, 3535, 4),
(2139, 'NAICS', 2037, 81, 1, 2131, 814, 2),
(2140, 'NAICS', 975, 4236, 3, 981, 42369, 4),
(2141, 'NAICS', 1625, 541, 2, 1690, 541810, 5),
(2142, 'NAICS', 1402, 51, 1, 1426, 512131, 5),
(2143, 'SIC', 3552, 3800, 2, 3560, 3825, 4),
(2144, 'SIC', 4040, 7300, 2, 4060, 7353, 4),
(2145, 'NAICS', 132, 21, 1, 149, 212222, 5),
(2146, 'NAICS', 930, 42, 1, 990, 42374, 4),
(2147, 'SIC', 3767, 5120, 3, 3768, 5122, 4),
(2148, 'NAICS', 1015, 424, 2, 1044, 424450, 5),
(2149, 'SEC', 2789, 10, 1, 2222, 1310, 3),
(2150, 'NAICS', 11, 11114, 4, 10, 111140, 5),
(2151, 'SIC', 3537, 3730, 3, 3539, 3732, 4),
(2152, 'SIC', 4311, 52, 1, 3840, 5520, 3),
(2153, 'NAICS', 931, 423, 2, 967, 42346, 4),
(2154, 'SIC', 3854, 5600, 2, 3862, 5641, 4),
(2155, 'SIC', 2825, 200, 2, 2831, 219, 4),
(2156, 'SEC', 2791, 20, 1, 2325, 2834, 4),
(2157, 'SIC', 4184, 8230, 3, 4185, 8231, 4),
(2158, 'NAICS', 1448, 51512, 4, 1447, 515120, 5),
(2159, 'SEC', 2713, 7300, 2, 2723, 7361, 4),
(2160, 'SIC', 3214, 2800, 2, 3235, 2850, 3),
(2161, 'SEC', 2797, 90, 1, 2786, 9720, 3),
(2162, 'SEC', 2618, 5410, 3, 2619, 5411, 4),
(2163, 'SIC', 3214, 2800, 2, 3234, 2844, 4),
(2164, 'SIC', 3214, 2800, 2, 3227, 2834, 4),
(2165, 'NAICS', 1513, 523, 2, 1524, 523210, 5),
(2166, 'SIC', 3349, 3330, 3, 3352, 3339, 4),
(2167, 'SIC', 4017, 7200, 2, 4024, 7217, 4),
(2168, 'SEC', 2476, 3800, 2, 2478, 3812, 4),
(2169, 'NAICS', 2038, 811, 2, 2039, 8111, 3),
(2170, 'SIC', 3552, 3800, 2, 3564, 3840, 3),
(2171, 'SIC', 4309, 40, 1, 3633, 4300, 2),
(2172, 'NAICS', 2135, 92, 1, 2170, 923120, 5),
(2173, 'SIC', 3311, 3250, 3, 3313, 3253, 4),
(2174, 'SIC', 3444, 3550, 3, 3447, 3554, 4),
(2175, 'SIC', 4310, 50, 1, 3800, 5193, 4),
(2176, 'NAICS', 2150, 922, 2, 2162, 922160, 5),
(2177, 'NAICS', 1958, 7113, 3, 1960, 71131, 4),
(2178, 'SIC', 4268, 9400, 2, 4271, 9430, 3),
(2179, 'SIC', 3762, 5100, 2, 3780, 5146, 4),
(2180, 'SIC', 4308, 20, 1, 3378, 3425, 4),
(2181, 'NAICS', 138, 212, 2, 165, 212324, 5),
(2182, 'SIC', 4049, 7330, 3, 4054, 7338, 4),
(2183, 'NAICS', 1624, 54, 1, 1625, 541, 2),
(2184, 'SIC', 2982, 2000, 2, 3005, 2046, 4),
(2185, 'NAICS', 1969, 712, 2, 1971, 712110, 5),
(2186, 'SIC', 3261, 3000, 2, 3275, 3083, 4),
(2187, 'NAICS', 205, 23, 1, 246, 23815, 4),
(2188, 'SIC', 4308, 20, 1, 3315, 3259, 4),
(2189, 'SIC', 4313, 70, 1, 4159, 8051, 4),
(2190, 'NAICS', 260, 2383, 3, 266, 23833, 4),
(2191, 'NAICS', 1812, 61, 1, 1847, 6117, 3),
(2192, 'SIC', 3322, 3270, 3, 3327, 3275, 4),
(2193, 'SIC', 4305, 1, 1, 2877, 912, 4),
(2194, 'SIC', 4309, 40, 1, 3611, 4130, 3),
(2195, 'SIC', 3740, 5060, 3, 3743, 5065, 4),
(2196, 'SIC', 4311, 52, 1, 3900, 5947, 4),
(2197, 'NAICS', 931, 423, 2, 959, 42342, 4),
(2198, 'NAICS', 1480, 52, 1, 1493, 522190, 5),
(2199, 'NAICS', 1904, 623, 2, 1915, 623311, 5),
(2200, 'SIC', 3050, 2200, 2, 3056, 2231, 4),
(2201, 'NAICS', 1453, 5171, 3, 1455, 51711, 4),
(2202, 'SIC', 3928, 6060, 3, 3930, 6062, 4),
(2203, 'SIC', 4181, 8220, 3, 4183, 8222, 4),
(2204, 'NAICS', 930, 42, 1, 1028, 42431, 4),
(2205, 'SIC', 3304, 3220, 3, 3305, 3221, 4),
(2206, 'NAICS', 1570, 531, 2, 1580, 5312, 3),
(2207, 'NAICS', 1725, 56, 1, 1790, 561990, 5),
(2208, 'NAICS', 1812, 61, 1, 1829, 61143, 4),
(2209, 'NAICS', 931, 423, 2, 991, 4238, 3),
(2210, 'NAICS', 1422, 51211, 4, 1421, 512110, 5),
(2211, 'NAICS', 2179, 92411, 4, 2178, 924110, 5),
(2212, 'SIC', 4309, 40, 1, 3682, 4812, 4),
(2213, 'SIC', 3911, 5990, 3, 3913, 5993, 4),
(2214, 'SIC', 4310, 50, 1, 3778, 5144, 4),
(2215, 'NAICS', 1813, 611, 2, 1823, 6114, 3),
(2216, 'NAICS', 1, 11, 1, 62, 11212, 4),
(2217, 'NAICS', 5, 11111, 4, 4, 111110, 5),
(2218, 'SIC', 4313, 70, 1, 4126, 7910, 3),
(2219, 'NAICS', 1035, 4244, 3, 1038, 424420, 5),
(2220, 'SEC', 2795, 60, 1, 2696, 6512, 4),
(2221, 'NAICS', 132, 21, 1, 136, 211111, 5),
(2222, 'SIC', 4313, 70, 1, 4236, 8741, 4),
(2223, 'NAICS', 1813, 611, 2, 1837, 611610, 5),
(2224, 'NAICS', 2004, 721, 2, 2005, 7211, 3),
(2225, 'NAICS', 1402, 51, 1, 1415, 511199, 5),
(2226, 'SIC', 4308, 20, 1, 3127, 2420, 3),
(2227, 'SIC', 4311, 52, 1, 3910, 5989, 4),
(2228, 'SIC', 2951, 1620, 3, 2954, 1629, 4),
(2229, 'SIC', 3083, 2300, 2, 3092, 2329, 4),
(2230, 'NAICS', 930, 42, 1, 1040, 424430, 5),
(2231, 'NAICS', 2103, 813, 2, 2120, 8139, 3),
(2232, 'SEC', 2342, 3000, 2, 2343, 3010, 3),
(2233, 'SIC', 3083, 2300, 2, 3121, 2396, 4),
(2234, 'SIC', 4309, 40, 1, 3668, 4720, 3),
(2235, 'SEC', 2713, 7300, 2, 2732, 7381, 4),
(2236, 'SIC', 3124, 2400, 2, 3135, 2436, 4),
(2237, 'NAICS', 235, 238, 2, 267, 238340, 5),
(2238, 'NAICS', 2037, 81, 1, 2095, 81291, 4),
(2239, 'SIC', 4311, 52, 1, 3906, 5963, 4),
(2240, 'SEC', 2512, 4000, 2, 2513, 4010, 3),
(2241, 'SEC', 2694, 6500, 2, 2697, 6513, 4),
(2242, 'NAICS', 1480, 52, 1, 1544, 524128, 5),
(2243, 'NAICS', 2090, 81233, 4, 2092, 812332, 5),
(2244, 'SIC', 4265, 9300, 2, 4267, 9311, 4),
(2245, 'NAICS', 205, 23, 1, 212, 236118, 5),
(2246, 'SIC', 3282, 3100, 2, 3292, 3150, 3),
(2247, 'NAICS', 932, 4231, 3, 938, 42313, 4),
(2248, 'NAICS', 1470, 519, 2, 1476, 519130, 5),
(2249, 'NAICS', 1598, 5322, 3, 1605, 53229, 4),
(2250, 'NAICS', 1624, 54, 1, 1695, 54183, 4),
(2251, 'SEC', 2753, 8000, 2, 2765, 8093, 4),
(2252, 'SEC', 2476, 3800, 2, 2477, 3810, 3),
(2253, 'SIC', 4314, 90, 1, 4291, 9640, 3),
(2254, 'SIC', 2975, 1790, 3, 2978, 1794, 4),
(2255, 'SIC', 2975, 1790, 3, 2979, 1795, 4),
(2256, 'SEC', 2342, 3000, 2, 2349, 3080, 3),
(2257, 'SEC', 2795, 60, 1, 2687, 6360, 3),
(2258, 'NAICS', 930, 42, 1, 1005, 423910, 5),
(2259, 'SIC', 3041, 2100, 2, 3045, 2121, 4),
(2260, 'SEC', 2791, 20, 1, 2245, 2020, 3),
(2261, 'NAICS', 1536, 524, 2, 1540, 524114, 5),
(2262, 'NAICS', 1402, 51, 1, 1432, 512210, 5),
(2263, 'NAICS', 1871, 6214, 3, 1875, 62142, 4),
(2264, 'NAICS', 1569, 53, 1, 1607, 532292, 5),
(2265, 'NAICS', 2150, 922, 2, 2155, 92212, 4),
(2266, 'SEC', 2403, 3500, 2, 2416, 3555, 4),
(2267, 'SEC', 2568, 5000, 2, 2575, 5045, 4),
(2268, 'SEC', 2796, 70, 1, 2725, 7370, 3),
(2269, 'SIC', 3886, 5900, 2, 3914, 5994, 4),
(2270, 'NAICS', 2, 111, 2, 50, 111940, 5),
(2271, 'NAICS', 1920, 624, 2, 1924, 624120, 5),
(2272, 'SIC', 4308, 20, 1, 3423, 3520, 3),
(2273, 'SIC', 3461, 3570, 3, 3465, 3577, 4),
(2274, 'SIC', 3636, 4400, 2, 3640, 4424, 4),
(2275, 'NAICS', 930, 42, 1, 955, 4234, 3),
(2276, 'NAICS', 1571, 5311, 3, 1579, 53119, 4),
(2277, 'SIC', 3434, 3540, 3, 3439, 3545, 4),
(2278, 'SIC', 4311, 52, 1, 3911, 5990, 3),
(2279, 'SIC', 4058, 7350, 3, 4059, 7352, 4),
(2280, 'NAICS', 117, 115, 2, 131, 11531, 4),
(2281, 'NAICS', 1480, 52, 1, 1497, 52221, 4),
(2282, 'SIC', 4309, 40, 1, 3637, 4410, 3),
(2283, 'NAICS', 182, 2211, 3, 194, 221122, 5),
(2284, 'NAICS', 930, 42, 1, 1066, 4247, 3),
(2285, 'NAICS', 65, 1122, 3, 66, 112210, 5),
(2286, 'NAICS', 1774, 5617, 3, 1781, 561740, 5),
(2287, 'SEC', 2796, 70, 1, 2740, 7812, 4),
(2288, 'SIC', 4306, 10, 1, 2917, 1389, 4),
(2289, 'SIC', 4312, 60, 1, 3951, 6220, 3),
(2290, 'NAICS', 1851, 621, 2, 1883, 621511, 5),
(2291, 'NAICS', 138, 212, 2, 142, 212112, 5),
(2292, 'SIC', 4308, 20, 1, 3047, 2131, 4),
(2293, 'NAICS', 1495, 5222, 3, 1501, 522291, 5),
(2294, 'SIC', 4308, 20, 1, 3291, 3149, 4),
(2295, 'NAICS', 15, 11116, 4, 14, 111160, 5),
(2296, 'NAICS', 1513, 523, 2, 1516, 52311, 4),
(2297, 'NAICS', 56, 112, 2, 82, 112420, 5),
(2298, 'NAICS', 1942, 71, 1, 1972, 71211, 4),
(2299, 'SIC', 3576, 3900, 2, 3589, 3952, 4),
(2300, 'NAICS', 943, 42321, 4, 942, 423210, 5),
(2301, 'SIC', 4178, 8200, 2, 4184, 8230, 3),
(2302, 'SEC', 2796, 70, 1, 2784, 8900, 2),
(2303, 'SIC', 3190, 2700, 2, 3210, 2789, 4),
(2304, 'NAICS', 2135, 92, 1, 2151, 9221, 3),
(2305, 'NAICS', 1593, 53211, 4, 1594, 532111, 5),
(2306, 'NAICS', 1402, 51, 1, 1434, 512220, 5),
(2307, 'NAICS', 110, 11411, 4, 111, 114111, 5),
(2308, 'SIC', 4308, 20, 1, 3599, 3996, 4),
(2309, 'SIC', 3480, 3600, 2, 3487, 3625, 4),
(2310, 'SIC', 4308, 20, 1, 3250, 2895, 4),
(2311, 'SIC', 4313, 70, 1, 4238, 8743, 4),
(2312, 'NAICS', 1562, 5259, 3, 1567, 525990, 5),
(2313, 'NAICS', 1404, 5111, 3, 1411, 511140, 5),
(2314, 'NAICS', 1733, 5613, 3, 1735, 561311, 5),
(2315, 'NAICS', 1850, 62, 1, 1918, 623990, 5),
(2316, 'SIC', 4313, 70, 1, 4088, 7521, 4),
(2317, 'NAICS', 162, 21232, 4, 166, 212325, 5),
(2318, 'SIC', 3200, 2750, 3, 3203, 2759, 4),
(2319, 'NAICS', 1526, 5239, 3, 1529, 523920, 5),
(2320, 'NAICS', 990, 42374, 4, 989, 423740, 5),
(2321, 'SIC', 4308, 20, 1, 3549, 3792, 4),
(2322, 'SIC', 3711, 4960, 3, 3712, 4961, 4),
(2323, 'SIC', 4308, 20, 1, 3464, 3575, 4),
(2324, 'SIC', 3762, 5100, 2, 3785, 5153, 4),
(2325, 'SIC', 4311, 52, 1, 3823, 5410, 3),
(2326, 'NAICS', 1624, 54, 1, 1643, 541320, 5),
(2327, 'SEC', 2796, 70, 1, 2736, 7510, 3),
(2328, 'SEC', 2403, 3500, 2, 2420, 3562, 4),
(2329, 'NAICS', 930, 42, 1, 1027, 424310, 5),
(2330, 'NAICS', 1726, 561, 2, 1772, 561621, 5),
(2331, 'NAICS', 205, 23, 1, 275, 23891, 4),
(2332, 'NAICS', 3, 1111, 3, 15, 11116, 4),
(2333, 'SIC', 4017, 7200, 2, 4033, 7250, 3),
(2334, 'NAICS', 1406, 51111, 4, 1405, 511110, 5),
(2335, 'NAICS', 1089, 425, 2, 1090, 4251, 3),
(2336, 'SIC', 4308, 20, 1, 3138, 2441, 4),
(2337, 'SIC', 3214, 2800, 2, 3247, 2891, 4),
(2338, 'NAICS', 260, 2383, 3, 264, 23832, 4),
(2339, 'SIC', 3067, 2260, 3, 3068, 2261, 4),
(2340, 'SIC', 4186, 8240, 3, 4188, 8244, 4),
(2341, 'NAICS', 2135, 92, 1, 2189, 9261, 3),
(2342, 'NAICS', 2004, 721, 2, 2017, 7213, 3),
(2343, 'NAICS', 1812, 61, 1, 1836, 6116, 3),
(2344, 'NAICS', 1480, 52, 1, 1562, 5259, 3),
(2345, 'SIC', 2912, 1320, 3, 2913, 1321, 4),
(2346, 'NAICS', 1550, 52429, 4, 1551, 524291, 5),
(2347, 'SIC', 3419, 3500, 2, 3472, 3586, 4),
(2348, 'SIC', 3680, 4800, 2, 3684, 4820, 3),
(2349, 'NAICS', 930, 42, 1, 962, 423440, 5),
(2350, 'NAICS', 931, 423, 2, 943, 42321, 4),
(2351, 'NAICS', 1402, 51, 1, 1421, 512110, 5),
(2352, 'NAICS', 1812, 61, 1, 1835, 611519, 5),
(2353, 'SIC', 4313, 70, 1, 4197, 8350, 3),
(2354, 'NAICS', 930, 42, 1, 953, 423390, 5),
(2355, 'SIC', 4308, 20, 1, 3210, 2789, 4),
(2356, 'SIC', 4308, 20, 1, 3520, 3690, 3),
(2357, 'NAICS', 1979, 713, 2, 1982, 71311, 4),
(2358, 'SEC', 2579, 5060, 3, 2581, 5064, 4),
(2359, 'SIC', 4314, 90, 1, 4258, 9211, 4),
(2360, 'NAICS', 1480, 52, 1, 1535, 523999, 5),
(2361, 'NAICS', 1753, 56145, 4, 1752, 561450, 5),
(2362, 'NAICS', 1725, 56, 1, 1758, 5615, 3),
(2363, 'NAICS', 2003, 72, 1, 2032, 72251, 4),
(2364, 'NAICS', 1402, 51, 1, 1442, 515, 2),
(2365, 'NAICS', 2201, 9271, 3, 2203, 92711, 4),
(2366, 'NAICS', 931, 423, 2, 982, 4237, 3),
(2367, 'NAICS', 1624, 54, 1, 1675, 541612, 5),
(2368, 'SEC', 2703, 6700, 2, 2704, 6790, 3),
(2369, 'SIC', 4308, 20, 1, 3324, 3272, 4),
(2370, 'SIC', 4313, 70, 1, 4223, 8700, 2),
(2371, 'NAICS', 2037, 81, 1, 2110, 813212, 5),
(2372, 'SIC', 3371, 3400, 2, 3376, 3421, 4),
(2373, 'SIC', 4308, 20, 1, 3164, 2590, 3),
(2374, 'NAICS', 930, 42, 1, 1068, 42471, 4),
(2375, 'SIC', 3693, 4900, 2, 3695, 4911, 4),
(2376, 'SIC', 3261, 3000, 2, 3263, 3011, 4),
(2377, 'NAICS', 2135, 92, 1, 2198, 926150, 5),
(2378, 'NAICS', 119, 11511, 4, 121, 115112, 5),
(2379, 'NAICS', 1813, 611, 2, 1844, 611691, 5),
(2380, 'SEC', 2391, 3440, 3, 2393, 3443, 4),
(2381, 'NAICS', 1726, 561, 2, 1748, 561431, 5),
(2382, 'NAICS', 240, 23812, 4, 239, 238120, 5),
(2383, 'NAICS', 1979, 713, 2, 1986, 713210, 5),
(2384, 'NAICS', 1625, 541, 2, 1704, 541890, 5),
(2385, 'SEC', 2240, 2000, 2, 2249, 2040, 3),
(2386, 'NAICS', 1871, 6214, 3, 1879, 621493, 5),
(2387, 'SEC', 2795, 60, 1, 4323, 6189, 4),
(2388, 'NAICS', 1851, 621, 2, 1891, 62199, 4),
(2389, 'SIC', 2962, 1740, 3, 2965, 1743, 4),
(2390, 'SIC', 3301, 3200, 2, 3315, 3259, 4),
(2391, 'SIC', 4308, 20, 1, 3412, 3493, 4),
(2392, 'SIC', 4313, 70, 1, 4203, 8400, 2),
(2393, 'SEC', 2434, 3600, 2, 2455, 3679, 4),
(2394, 'SIC', 4309, 40, 1, 3669, 4724, 4),
(2395, 'SIC', 3149, 2510, 3, 3154, 2517, 4),
(2396, 'NAICS', 1850, 62, 1, 1928, 6242, 3),
(2397, 'SIC', 4313, 70, 1, 4052, 7335, 4),
(2398, 'SIC', 3337, 3300, 2, 3341, 3315, 4),
(2399, 'SIC', 4309, 40, 1, 3686, 4830, 3),
(2400, 'NAICS', 2061, 8114, 3, 2062, 81141, 4),
(2401, 'SIC', 3409, 3490, 3, 3410, 3491, 4),
(2402, 'NAICS', 180, 22, 1, 204, 22133, 4),
(2403, 'SEC', 2305, 2720, 3, 2306, 2721, 4),
(2404, 'SEC', 2791, 20, 1, 2267, 2250, 3),
(2405, 'SEC', 2791, 20, 1, 2468, 3728, 4),
(2406, 'SIC', 3769, 5130, 3, 3772, 5137, 4),
(2407, 'SEC', 2703, 6700, 2, 2705, 6792, 4),
(2408, 'SIC', 4308, 20, 1, 3222, 2822, 4),
(2409, 'NAICS', 1876, 62149, 4, 1877, 621491, 5),
(2410, 'SIC', 3220, 2820, 3, 3222, 2822, 4),
(2411, 'SIC', 3272, 3080, 3, 3275, 3083, 4),
(2412, 'NAICS', 56, 112, 2, 91, 11291, 4),
(2413, 'SIC', 3870, 5710, 3, 3874, 5719, 4),
(2414, 'NAICS', 946, 4233, 3, 947, 423310, 5),
(2415, 'SIC', 3822, 5400, 2, 3836, 5499, 4),
(2416, 'NAICS', 1419, 512, 2, 1425, 51213, 4),
(2417, 'NAICS', 1830, 6115, 3, 1835, 611519, 5),
(2418, 'NAICS', 1794, 56211, 4, 1795, 562111, 5),
(2419, 'SIC', 3740, 5060, 3, 3742, 5064, 4),
(2420, 'NAICS', 2038, 811, 2, 2053, 81121, 4),
(2421, 'SEC', 2650, 6020, 3, 2651, 6021, 4),
(2422, 'SIC', 4308, 20, 1, 3424, 3523, 4),
(2423, 'NAICS', 180, 22, 1, 195, 2212, 3),
(2424, 'NAICS', 1624, 54, 1, 1685, 541711, 5),
(2425, 'NAICS', 114, 1142, 3, 116, 11421, 4),
(2426, 'NAICS', 1936, 6243, 3, 1938, 62431, 4),
(2427, 'SIC', 3148, 2500, 2, 3150, 2511, 4),
(2428, 'SIC', 4049, 7330, 3, 4051, 7334, 4),
(2429, 'SIC', 4313, 70, 1, 4121, 7832, 4),
(2430, 'NAICS', 1402, 51, 1, 1436, 512230, 5),
(2431, 'SIC', 4308, 20, 1, 3559, 3824, 4),
(2432, 'SEC', 2791, 20, 1, 2455, 3679, 4),
(2433, 'NAICS', 1480, 52, 1, 1504, 522294, 5),
(2434, 'SIC', 3041, 2100, 2, 3048, 2140, 3),
(2435, 'NAICS', 1812, 61, 1, 1848, 611710, 5),
(2436, 'SEC', 2505, 3940, 3, 2508, 3949, 4),
(2437, 'SEC', 2385, 3410, 3, 2386, 3411, 4),
(2438, 'SIC', 4313, 70, 1, 4045, 7319, 4),
(2439, 'SEC', 4336, 99, 1, 4337, 8880, 2),
(2440, 'SIC', 3375, 3420, 3, 3379, 3429, 4),
(2441, 'SIC', 4314, 90, 1, 4292, 9641, 4),
(2442, 'NAICS', 1774, 5617, 3, 1779, 561730, 5),
(2443, 'SEC', 2591, 5100, 2, 2599, 5160, 3),
(2444, 'SIC', 4284, 9600, 2, 4294, 9651, 4),
(2445, 'NAICS', 1792, 562, 2, 1793, 5621, 3),
(2446, 'SEC', 2792, 40, 1, 2514, 4011, 4),
(2447, 'SIC', 4100, 7600, 2, 4105, 7630, 3),
(2448, 'SEC', 2271, 2300, 2, 2275, 2390, 3),
(2449, 'SIC', 2918, 1400, 2, 2925, 1440, 3),
(2450, 'SIC', 4308, 20, 1, 3038, 2097, 4),
(2451, 'SIC', 4223, 8700, 2, 4230, 8730, 3),
(2452, 'NAICS', 955, 4234, 3, 958, 423420, 5),
(2453, 'SEC', 2794, 52, 1, 2636, 5735, 4),
(2454, 'SEC', 2791, 20, 1, 2420, 3562, 4),
(2455, 'SIC', 4308, 20, 1, 3136, 2439, 4),
(2456, 'SIC', 2918, 1400, 2, 2936, 1481, 4),
(2457, 'NAICS', 1741, 5614, 3, 1756, 561492, 5),
(2458, 'SIC', 4146, 8000, 2, 4153, 8040, 3),
(2459, 'NAICS', 1913, 6233, 3, 1916, 623312, 5),
(2460, 'SIC', 2982, 2000, 2, 3010, 2052, 4),
(2461, 'NAICS', 1853, 62111, 4, 1855, 621112, 5),
(2462, 'NAICS', 1730, 5612, 3, 1731, 561210, 5),
(2463, 'SIC', 4308, 20, 1, 3009, 2051, 4),
(2464, 'SIC', 3887, 5910, 3, 3888, 5912, 4),
(2465, 'NAICS', 1850, 62, 1, 1921, 6241, 3),
(2466, 'NAICS', 2037, 81, 1, 2051, 811198, 5),
(2467, 'SEC', 2257, 2090, 3, 2258, 2092, 4),
(2468, 'NAICS', 1471, 5191, 3, 1476, 519130, 5),
(2469, 'SEC', 2796, 70, 1, 2728, 7373, 4),
(2470, 'SIC', 2871, 830, 3, 2872, 831, 4),
(2471, 'SEC', 2450, 3670, 3, 2454, 3678, 4),
(2472, 'SIC', 3977, 6500, 2, 3986, 6531, 4),
(2473, 'NAICS', 2037, 81, 1, 2062, 81141, 4),
(2474, 'SIC', 4010, 7020, 3, 4011, 7021, 4),
(2475, 'NAICS', 2005, 7211, 3, 2007, 72111, 4),
(2476, 'NAICS', 2, 111, 2, 28, 11133, 4),
(2477, 'NAICS', 1433, 51221, 4, 1432, 512210, 5),
(2478, 'NAICS', 1612, 5324, 3, 1618, 532490, 5),
(2479, 'SIC', 4178, 8200, 2, 4180, 8211, 4),
(2480, 'NAICS', 49, 11193, 4, 48, 111930, 5),
(2481, 'SIC', 3419, 3500, 2, 3422, 3519, 4),
(2482, 'NAICS', 2037, 81, 1, 2057, 811219, 5),
(2483, 'NAICS', 1689, 5418, 3, 1704, 541890, 5),
(2484, 'NAICS', 180, 22, 1, 197, 22121, 4),
(2485, 'SEC', 2774, 8700, 2, 2782, 8742, 4),
(2486, 'SIC', 2873, 850, 3, 2874, 851, 4),
(2487, 'SIC', 2884, 1000, 2, 2885, 1010, 3),
(2488, 'SEC', 2241, 2010, 3, 2244, 2015, 4),
(2489, 'SEC', 2667, 6160, 3, 2669, 6163, 4),
(2490, 'SIC', 2825, 200, 2, 2839, 259, 4),
(2491, 'SIC', 4308, 20, 1, 3557, 3822, 4),
(2492, 'NAICS', 1725, 56, 1, 1782, 56174, 4),
(2493, 'SIC', 4308, 20, 1, 3329, 3281, 4),
(2494, 'SIC', 3371, 3400, 2, 3418, 3499, 4),
(2495, 'SIC', 3261, 3000, 2, 3268, 3053, 4),
(2496, 'SIC', 4199, 8360, 3, 4200, 8361, 4),
(2497, 'NAICS', 1480, 52, 1, 1547, 5242, 3),
(2498, 'NAICS', 2096, 81292, 4, 2097, 812921, 5),
(2499, 'SIC', 3762, 5100, 2, 3799, 5192, 4),
(2500, 'NAICS', 1452, 517, 2, 1454, 517110, 5),
(2501, 'SEC', 2659, 6100, 2, 4340, 6172, 4),
(2502, 'SIC', 2939, 1500, 2, 2940, 1520, 3),
(2503, 'SEC', 2443, 3650, 3, 2445, 3652, 4),
(2504, 'SIC', 3636, 4400, 2, 3638, 4412, 4),
(2505, 'SIC', 4308, 20, 1, 3050, 2200, 2),
(2506, 'SIC', 3148, 2500, 2, 3165, 2591, 4),
(2507, 'SIC', 3237, 2860, 3, 3239, 2865, 4),
(2508, 'NAICS', 1015, 424, 2, 1084, 42494, 4),
(2509, 'NAICS', 2205, 9281, 3, 2206, 928110, 5),
(2510, 'SIC', 2909, 1300, 2, 2915, 1381, 4),
(2511, 'NAICS', 1402, 51, 1, 1464, 517911, 5),
(2512, 'NAICS', 1725, 56, 1, 1754, 56149, 4),
(2513, 'NAICS', 2037, 81, 1, 2052, 8112, 3),
(2514, 'SIC', 3520, 3690, 3, 3523, 3694, 4),
(2515, 'NAICS', 43, 1119, 3, 47, 11192, 4),
(2516, 'NAICS', 1726, 561, 2, 1727, 5611, 3),
(2517, 'SIC', 4278, 9510, 3, 4280, 9512, 4),
(2518, 'SIC', 4311, 52, 1, 3808, 5231, 4),
(2519, 'NAICS', 1850, 62, 1, 1857, 621210, 5),
(2520, 'SEC', 2262, 2200, 2, 2266, 2221, 4),
(2521, 'SIC', 2840, 270, 3, 2844, 279, 4),
(2522, 'SIC', 3272, 3080, 3, 3280, 3088, 4),
(2523, 'NAICS', 1591, 532, 2, 1611, 53231, 4),
(2524, 'SIC', 4313, 70, 1, 4144, 7997, 4),
(2525, 'SEC', 2300, 2670, 3, 2301, 2673, 4),
(2526, 'SIC', 4308, 20, 1, 3437, 3543, 4),
(2527, 'SEC', 2335, 2890, 3, 2336, 2891, 4),
(2528, 'SIC', 4311, 52, 1, 3903, 5960, 3),
(2529, 'SIC', 4310, 50, 1, 3754, 5087, 4),
(2530, 'SIC', 4305, 1, 1, 2864, 780, 3),
(2531, 'SIC', 4305, 1, 1, 2847, 700, 2),
(2532, 'SIC', 4308, 20, 1, 3144, 2490, 3),
(2533, 'NAICS', 235, 238, 2, 245, 238150, 5),
(2534, 'NAICS', 2, 111, 2, 4, 111110, 5),
(2535, 'NAICS', 232, 2379, 3, 233, 237990, 5),
(2536, 'SIC', 4265, 9300, 2, 4266, 9310, 3),
(2537, 'NAICS', 1733, 5613, 3, 1739, 561330, 5),
(2538, 'SIC', 4278, 9510, 3, 4279, 9511, 4),
(2539, 'NAICS', 1726, 561, 2, 1732, 56121, 4),
(2540, 'NAICS', 2037, 81, 1, 2128, 81394, 4),
(2541, 'SIC', 4308, 20, 1, 3372, 3410, 3),
(2542, 'SIC', 3371, 3400, 2, 3388, 3444, 4),
(2543, 'SEC', 2630, 5700, 2, 2635, 5734, 4),
(2544, 'NAICS', 1718, 55, 1, 1723, 551112, 5),
(2545, 'SIC', 3576, 3900, 2, 3586, 3949, 4),
(2546, 'SIC', 4308, 20, 1, 3225, 2830, 3),
(2547, 'SEC', 2593, 5120, 3, 2594, 5122, 4),
(2548, 'SIC', 4308, 20, 1, 3456, 3565, 4),
(2549, 'SIC', 3893, 5940, 3, 3902, 5949, 4),
(2550, 'NAICS', 1016, 4241, 3, 1022, 42413, 4),
(2551, 'SEC', 2479, 3820, 3, 2484, 3825, 4),
(2552, 'SEC', 2794, 52, 1, 2637, 5800, 2),
(2553, 'SIC', 4125, 7900, 2, 4130, 7929, 4),
(2554, 'NAICS', 1480, 52, 1, 1511, 522390, 5),
(2555, 'NAICS', 1851, 621, 2, 1859, 6213, 3),
(2556, 'SIC', 2898, 1090, 3, 2899, 1094, 4),
(2557, 'SIC', 3526, 3700, 2, 3533, 3720, 3),
(2558, 'NAICS', 91, 11291, 4, 90, 112910, 5),
(2559, 'NAICS', 1471, 5191, 3, 1475, 51912, 4),
(2560, 'NAICS', 2004, 721, 2, 2007, 72111, 4),
(2561, 'SEC', 2569, 5010, 3, 2570, 5013, 4),
(2562, 'NAICS', 266, 23833, 4, 265, 238330, 5),
(2563, 'NAICS', 1904, 623, 2, 1912, 62322, 4),
(2564, 'SIC', 4308, 20, 1, 3316, 3260, 3),
(2565, 'NAICS', 2137, 9211, 3, 2140, 921120, 5),
(2566, 'SEC', 2476, 3800, 2, 2489, 3841, 4),
(2567, 'SIC', 3583, 3940, 3, 3585, 3944, 4),
(2568, 'SIC', 3667, 4700, 2, 3676, 4780, 3),
(2569, 'SIC', 3086, 2320, 3, 3091, 2326, 4),
(2570, 'SIC', 4271, 9430, 3, 4272, 9431, 4),
(2571, 'SIC', 2982, 2000, 2, 3021, 2074, 4),
(2572, 'NAICS', 2135, 92, 1, 2142, 921130, 5),
(2573, 'SIC', 4308, 20, 1, 3008, 2050, 3),
(2574, 'SIC', 3255, 2950, 3, 3257, 2952, 4),
(2575, 'SIC', 3886, 5900, 2, 3899, 5946, 4),
(2576, 'NAICS', 89, 1129, 3, 91, 11291, 4),
(2577, 'SEC', 2791, 20, 1, 2427, 3575, 4),
(2578, 'NAICS', 1015, 424, 2, 1028, 42431, 4),
(2579, 'SIC', 3854, 5600, 2, 3859, 5630, 3),
(2580, 'NAICS', 1706, 5419, 3, 1707, 541910, 5),
(2581, 'SIC', 4284, 9600, 2, 4285, 9610, 3),
(2582, 'SIC', 4308, 20, 1, 3185, 2675, 4),
(2583, 'NAICS', 1850, 62, 1, 1909, 623210, 5),
(2584, 'SIC', 4308, 20, 1, 3228, 2835, 4),
(2585, 'NAICS', 930, 42, 1, 986, 42372, 4),
(2586, 'NAICS', 1015, 424, 2, 1040, 424430, 5),
(2587, 'SIC', 4308, 20, 1, 3219, 2819, 4),
(2588, 'NAICS', 1513, 523, 2, 1519, 523130, 5),
(2589, 'SIC', 2931, 1470, 3, 2934, 1479, 4),
(2590, 'SEC', 2568, 5000, 2, 2586, 5082, 4),
(2591, 'NAICS', 1852, 6211, 3, 1853, 62111, 4),
(2592, 'SIC', 2918, 1400, 2, 2928, 1450, 3),
(2593, 'SEC', 2319, 2800, 2, 2328, 2840, 3),
(2594, 'SIC', 4313, 70, 1, 4135, 7948, 4),
(2595, 'SIC', 4305, 1, 1, 2858, 750, 3),
(2596, 'SIC', 4310, 50, 1, 3789, 5162, 4),
(2597, 'SIC', 4308, 20, 1, 3505, 3651, 4),
(2598, 'NAICS', 1016, 4241, 3, 1018, 42411, 4),
(2599, 'NAICS', 1871, 6214, 3, 1876, 62149, 4),
(2600, 'SIC', 2982, 2000, 2, 3032, 2087, 4),
(2601, 'SIC', 3838, 5510, 3, 3839, 5511, 4),
(2602, 'NAICS', 1813, 611, 2, 1827, 61142, 4),
(2603, 'SIC', 3167, 2600, 2, 3186, 2676, 4),
(2604, 'SEC', 2791, 20, 1, 2437, 3613, 4),
(2605, 'NAICS', 205, 23, 1, 259, 23829, 4),
(2606, 'SIC', 4306, 10, 1, 2890, 1031, 4),
(2607, 'SIC', 4040, 7300, 2, 4072, 7377, 4),
(2608, 'NAICS', 1758, 5615, 3, 1760, 56151, 4),
(2609, 'SEC', 2792, 40, 1, 2563, 4941, 4),
(2610, 'SEC', 2643, 5940, 3, 2644, 5944, 4),
(2611, 'NAICS', 1726, 561, 2, 1735, 561311, 5),
(2612, 'NAICS', 930, 42, 1, 1044, 424450, 5),
(2613, 'NAICS', 1456, 5172, 3, 1457, 517210, 5),
(2614, 'SIC', 3282, 3100, 2, 3298, 3172, 4),
(2615, 'SIC', 3272, 3080, 3, 3278, 3086, 4),
(2616, 'SIC', 3241, 2870, 3, 3244, 2875, 4),
(2617, 'SIC', 4065, 7370, 3, 4066, 7371, 4),
(2618, 'SEC', 2793, 50, 1, 2576, 5047, 4),
(2619, 'SIC', 4314, 90, 1, 4256, 9200, 2),
(2620, 'SIC', 3419, 3500, 2, 3428, 3532, 4),
(2621, 'NAICS', 1970, 7121, 3, 1978, 71219, 4),
(2622, 'NAICS', 181, 221, 2, 184, 221111, 5),
(2623, 'NAICS', 1480, 52, 1, 1526, 5239, 3),
(2624, 'SIC', 4027, 7220, 3, 4028, 7221, 4),
(2625, 'SEC', 2476, 3800, 2, 2483, 3824, 4),
(2626, 'SIC', 4312, 60, 1, 3972, 6390, 3),
(2627, 'SIC', 3663, 4610, 3, 3666, 4619, 4),
(2628, 'SIC', 4139, 7990, 3, 4144, 7997, 4),
(2629, 'SIC', 4146, 8000, 2, 4158, 8050, 3),
(2630, 'NAICS', 1812, 61, 1, 1830, 6115, 3),
(2631, 'NAICS', 2135, 92, 1, 2166, 923, 2),
(2632, 'SEC', 2791, 20, 1, 2337, 2900, 2),
(2633, 'SIC', 4277, 9500, 2, 4282, 9531, 4),
(2634, 'SIC', 4146, 8000, 2, 4160, 8052, 4),
(2635, 'SEC', 2283, 2500, 2, 2290, 2540, 3),
(2636, 'NAICS', 56, 112, 2, 78, 11239, 4),
(2637, 'NAICS', 114, 1142, 3, 115, 114210, 5),
(2638, 'NAICS', 1725, 56, 1, 1736, 561312, 5),
(2639, 'SIC', 3942, 6150, 3, 3943, 6153, 4),
(2640, 'NAICS', 2188, 926, 2, 2191, 92611, 4),
(2641, 'NAICS', 1851, 621, 2, 1870, 621399, 5),
(2642, 'SIC', 4307, 15, 1, 2972, 1771, 4),
(2643, 'SIC', 3693, 4900, 2, 3709, 4953, 4),
(2644, 'SEC', 2229, 1500, 2, 2232, 1531, 4),
(2645, 'SIC', 4308, 20, 1, 3004, 2045, 4),
(2646, 'SIC', 4308, 20, 1, 3014, 2062, 4),
(2647, 'NAICS', 218, 237, 2, 233, 237990, 5),
(2648, 'SEC', 2796, 70, 1, 2735, 7500, 2),
(2649, 'NAICS', 1812, 61, 1, 1826, 611420, 5),
(2650, 'NAICS', 2037, 81, 1, 2099, 812930, 5),
(2651, 'SIC', 4308, 20, 1, 3024, 2077, 4),
(2652, 'SEC', 2263, 2210, 3, 2264, 2211, 4),
(2653, 'SEC', 2434, 3600, 2, 2447, 3661, 4),
(2654, 'SIC', 4308, 20, 1, 3293, 3151, 4),
(2655, 'SIC', 3419, 3500, 2, 3447, 3554, 4),
(2656, 'SIC', 3301, 3200, 2, 3331, 3291, 4),
(2657, 'SIC', 4312, 60, 1, 4005, 6798, 4),
(2658, 'NAICS', 1851, 621, 2, 1868, 62139, 4),
(2659, 'NAICS', 1850, 62, 1, 1907, 62311, 4),
(2660, 'SIC', 3086, 2320, 3, 3089, 2323, 4),
(2661, 'NAICS', 2020, 722, 2, 2027, 72233, 4),
(2662, 'NAICS', 1004, 4239, 3, 1009, 423930, 5),
(2663, 'NAICS', 126, 1152, 3, 128, 11521, 4),
(2664, 'SIC', 4308, 20, 1, 3075, 2282, 4),
(2665, 'SIC', 3564, 3840, 3, 3569, 3845, 4),
(2666, 'SEC', 2791, 20, 1, 2414, 3541, 4),
(2667, 'NAICS', 1850, 62, 1, 1886, 621610, 5),
(2668, 'NAICS', 2135, 92, 1, 2205, 9281, 3),
(2669, 'SEC', 2791, 20, 1, 2334, 2870, 3),
(2670, 'NAICS', 2037, 81, 1, 2039, 8111, 3),
(2671, 'NAICS', 1920, 624, 2, 1927, 62419, 4),
(2672, 'SEC', 2704, 6790, 3, 2705, 6792, 4),
(2673, 'SEC', 2633, 5730, 3, 2636, 5735, 4),
(2674, 'NAICS', 1850, 62, 1, 1908, 6232, 3),
(2675, 'NAICS', 1598, 5322, 3, 1607, 532292, 5),
(2676, 'SIC', 4311, 52, 1, 3859, 5630, 3),
(2677, 'SEC', 2795, 60, 1, 2703, 6700, 2),
(2678, 'SIC', 2847, 700, 2, 2856, 741, 4),
(2679, 'NAICS', 1725, 56, 1, 1742, 561410, 5),
(2680, 'SEC', 2621, 5530, 3, 2622, 5531, 4),
(2681, 'NAICS', 1570, 531, 2, 1590, 53139, 4),
(2682, 'SIC', 4310, 50, 1, 3798, 5191, 4),
(2683, 'SIC', 4310, 50, 1, 3787, 5159, 4),
(2684, 'SIC', 3762, 5100, 2, 3763, 5110, 3),
(2685, 'NAICS', 207, 2361, 3, 211, 236117, 5),
(2686, 'SEC', 2791, 20, 1, 2447, 3661, 4),
(2687, 'SIC', 4308, 20, 1, 3407, 3484, 4),
(2688, 'SIC', 4314, 90, 1, 4295, 9660, 3),
(2689, 'NAICS', 1939, 6244, 3, 1940, 624410, 5),
(2690, 'SIC', 3797, 5190, 3, 3801, 5194, 4),
(2691, 'SEC', 2795, 60, 1, 2693, 6411, 4),
(2692, 'NAICS', 1550, 52429, 4, 1553, 524298, 5),
(2693, 'SIC', 4308, 20, 1, 3172, 2630, 3),
(2694, 'NAICS', 1814, 6111, 3, 1816, 61111, 4),
(2695, 'NAICS', 1726, 561, 2, 1739, 561330, 5),
(2696, 'SIC', 3937, 6100, 2, 3942, 6150, 3),
(2697, 'NAICS', 1625, 541, 2, 1676, 541613, 5),
(2698, 'SIC', 4305, 1, 1, 2863, 762, 4),
(2699, 'NAICS', 931, 423, 2, 936, 42312, 4),
(2700, 'NAICS', 1402, 51, 1, 1474, 519120, 5),
(2701, 'NAICS', 1569, 53, 1, 1605, 53229, 4),
(2702, 'SIC', 4224, 8710, 3, 4226, 8712, 4),
(2703, 'NAICS', 132, 21, 1, 165, 212324, 5),
(2704, 'NAICS', 144, 2122, 3, 152, 212234, 5),
(2705, 'NAICS', 1513, 523, 2, 1530, 52392, 4),
(2706, 'SEC', 2517, 4200, 2, 2519, 4213, 4),
(2707, 'SIC', 4313, 70, 1, 4099, 7549, 4),
(2708, 'SIC', 4230, 8730, 3, 4233, 8733, 4),
(2709, 'NAICS', 1684, 54171, 4, 1685, 541711, 5),
(2710, 'SIC', 3384, 3440, 3, 3389, 3446, 4),
(2711, 'NAICS', 1812, 61, 1, 1821, 611310, 5),
(2712, 'NAICS', 1442, 515, 2, 1451, 51521, 4),
(2713, 'SIC', 4151, 8030, 3, 4152, 8031, 4),
(2714, 'NAICS', 1, 11, 1, 48, 111930, 5),
(2715, 'SEC', 2790, 15, 1, 2238, 1730, 3),
(2716, 'SEC', 2695, 6510, 3, 2697, 6513, 4),
(2717, 'SIC', 3744, 5070, 3, 3748, 5078, 4),
(2718, 'NAICS', 3, 1111, 3, 12, 111150, 5),
(2719, 'NAICS', 1035, 4244, 3, 1039, 42442, 4),
(2720, 'NAICS', 2085, 8123, 3, 2087, 81231, 4),
(2721, 'SEC', 2568, 5000, 2, 2582, 5065, 4),
(2722, 'SIC', 3480, 3600, 2, 3501, 3646, 4),
(2723, 'NAICS', 1680, 54162, 4, 1679, 541620, 5),
(2724, 'SEC', 2770, 8300, 2, 2772, 8351, 4),
(2725, 'SIC', 3526, 3700, 2, 3541, 3743, 4),
(2726, 'SIC', 4313, 70, 1, 4068, 7373, 4),
(2727, 'NAICS', 1950, 71113, 4, 1949, 711130, 5),
(2728, 'SIC', 4307, 15, 1, 2949, 1610, 3),
(2729, 'NAICS', 264, 23832, 4, 263, 238320, 5),
(2730, 'NAICS', 1804, 5629, 3, 1807, 562920, 5),
(2731, 'NAICS', 1813, 611, 2, 1849, 61171, 4),
(2732, 'SIC', 3701, 4930, 3, 3702, 4931, 4),
(2733, 'NAICS', 1785, 5619, 3, 1789, 56192, 4),
(2734, 'SIC', 3592, 3960, 3, 3594, 3965, 4),
(2735, 'SEC', 2434, 3600, 2, 2437, 3613, 4),
(2736, 'SIC', 3996, 6720, 3, 3998, 6726, 4),
(2737, 'NAICS', 1673, 54161, 4, 1677, 541614, 5),
(2738, 'SEC', 2403, 3500, 2, 2427, 3575, 4),
(2739, 'SIC', 4305, 1, 1, 2859, 751, 4),
(2740, 'SIC', 4313, 70, 1, 4167, 8071, 4),
(2741, 'NAICS', 1850, 62, 1, 1925, 62412, 4),
(2742, 'SIC', 4312, 60, 1, 3982, 6515, 4),
(2743, 'SIC', 3371, 3400, 2, 3403, 3479, 4),
(2744, 'SIC', 4287, 9620, 3, 4288, 9621, 4),
(2745, 'SIC', 4307, 15, 1, 2980, 1796, 4),
(2746, 'SIC', 3837, 5500, 2, 3844, 5540, 3),
(2747, 'NAICS', 138, 212, 2, 149, 212222, 5),
(2748, 'SIC', 4312, 60, 1, 3932, 6081, 4),
(2749, 'SEC', 2795, 60, 1, 2654, 6030, 3),
(2750, 'NAICS', 1625, 541, 2, 1717, 54199, 4),
(2751, 'NAICS', 1538, 52411, 4, 1539, 524113, 5),
(2752, 'SIC', 4310, 50, 1, 3790, 5169, 4),
(2753, 'NAICS', 1497, 52221, 4, 1496, 522210, 5),
(2754, 'SIC', 4308, 20, 1, 3480, 3600, 2),
(2755, 'NAICS', 1569, 53, 1, 1587, 531320, 5),
(2756, 'NAICS', 1720, 5511, 3, 1721, 55111, 4),
(2757, 'NAICS', 1830, 6115, 3, 1833, 611512, 5),
(2758, 'SIC', 3729, 5040, 3, 3733, 5046, 4),
(2759, 'NAICS', 1725, 56, 1, 1749, 561439, 5),
(2760, 'NAICS', 146, 21221, 4, 145, 212210, 5),
(2761, 'NAICS', 253, 2382, 3, 257, 23822, 4),
(2762, 'NAICS', 2120, 8139, 3, 2129, 813990, 5),
(2763, 'SIC', 4065, 7370, 3, 4074, 7379, 4),
(2764, 'SIC', 4313, 70, 1, 4107, 7640, 3),
(2765, 'NAICS', 206, 236, 2, 211, 236117, 5),
(2766, 'NAICS', 1015, 424, 2, 1058, 42452, 4),
(2767, 'NAICS', 1609, 5323, 3, 1611, 53231, 4),
(2768, 'NAICS', 1904, 623, 2, 1919, 62399, 4),
(2769, 'SIC', 4308, 20, 1, 3122, 2397, 4),
(2770, 'NAICS', 1419, 512, 2, 1420, 5121, 3),
(2771, 'SEC', 2262, 2200, 2, 2265, 2220, 3),
(2772, 'NAICS', 1480, 52, 1, 1481, 521, 2),
(2773, 'NAICS', 2134, 81411, 4, 2133, 814110, 5),
(2774, 'SIC', 3012, 2060, 3, 3016, 2064, 4),
(2775, 'NAICS', 2014, 72121, 4, 2016, 721214, 5),
(2776, 'SIC', 4311, 52, 1, 3835, 5490, 3),
(2777, 'NAICS', 1725, 56, 1, 1768, 561611, 5),
(2778, 'SIC', 3552, 3800, 2, 3572, 3860, 3),
(2779, 'SIC', 4314, 90, 1, 4268, 9400, 2),
(2780, 'SIC', 4308, 20, 1, 3135, 2436, 4),
(2781, 'SIC', 4305, 1, 1, 2800, 111, 4),
(2782, 'SEC', 2753, 8000, 2, 2754, 8010, 3),
(2783, 'SIC', 2884, 1000, 2, 2895, 1061, 4),
(2784, 'SEC', 2458, 3700, 2, 2474, 3760, 3),
(2785, 'SIC', 3444, 3550, 3, 3448, 3555, 4),
(2786, 'NAICS', 1583, 5313, 3, 1588, 53132, 4),
(2787, 'SEC', 2623, 5600, 2, 2629, 5661, 4),
(2788, 'NAICS', 1569, 53, 1, 1571, 5311, 3),
(2789, 'SIC', 3822, 5400, 2, 3831, 5450, 3),
(2790, 'NAICS', 1767, 56161, 4, 1770, 561613, 5),
(2791, 'NAICS', 200, 22131, 4, 199, 221310, 5),
(2792, 'NAICS', 1569, 53, 1, 1578, 531190, 5),
(2793, 'SIC', 3131, 2430, 3, 3133, 2434, 4),
(2794, 'SIC', 4305, 1, 1, 2873, 850, 3),
(2795, 'NAICS', 2, 111, 2, 14, 111160, 5),
(2796, 'SEC', 2459, 3710, 3, 2462, 3714, 4),
(2797, 'SIC', 4313, 70, 1, 4120, 7830, 3),
(2798, 'SIC', 3484, 3620, 3, 3488, 3629, 4),
(2799, 'SIC', 4312, 60, 1, 3976, 6411, 4),
(2800, 'SIC', 3371, 3400, 2, 3411, 3492, 4),
(2801, 'SEC', 2792, 40, 1, 2513, 4010, 3),
(2802, 'SIC', 4125, 7900, 2, 4126, 7910, 3),
(2803, 'SIC', 4192, 8300, 2, 4198, 8351, 4),
(2804, 'SIC', 3124, 2400, 2, 3127, 2420, 3),
(2805, 'NAICS', 68, 1123, 3, 73, 112330, 5),
(2806, 'SIC', 3537, 3730, 3, 3538, 3731, 4),
(2807, 'SIC', 4308, 20, 1, 3292, 3150, 3),
(2808, 'NAICS', 2003, 72, 1, 2031, 7225, 3),
(2809, 'SIC', 4308, 20, 1, 3253, 2910, 3),
(2810, 'NAICS', 1039, 42442, 4, 1038, 424420, 5),
(2811, 'NAICS', 1624, 54, 1, 1671, 541519, 5),
(2812, 'NAICS', 2135, 92, 1, 2190, 926110, 5),
(2813, 'NAICS', 931, 423, 2, 1002, 423860, 5),
(2814, 'NAICS', 2135, 92, 1, 2152, 922110, 5),
(2815, 'SIC', 4308, 20, 1, 3173, 2631, 4),
(2816, 'SIC', 4224, 8710, 3, 4227, 8713, 4),
(2817, 'SIC', 3489, 3630, 3, 3494, 3635, 4),
(2818, 'SEC', 2241, 2010, 3, 2243, 2013, 4),
(2819, 'SIC', 3762, 5100, 2, 3773, 5139, 4),
(2820, 'SIC', 4310, 50, 1, 3726, 5032, 4),
(2821, 'SIC', 4313, 70, 1, 4065, 7370, 3),
(2822, 'SEC', 2722, 7360, 3, 2723, 7361, 4),
(2823, 'NAICS', 1015, 424, 2, 1053, 42449, 4),
(2824, 'NAICS', 1812, 61, 1, 1833, 611512, 5),
(2825, 'NAICS', 1015, 424, 2, 1057, 424520, 5),
(2826, 'SEC', 2391, 3440, 3, 2394, 3444, 4),
(2827, 'SEC', 2403, 3500, 2, 2414, 3541, 4),
(2828, 'SIC', 3480, 3600, 2, 3489, 3630, 3),
(2829, 'NAICS', 1442, 515, 2, 1449, 5152, 3),
(2830, 'SEC', 2795, 60, 1, 2649, 6000, 2),
(2831, 'SEC', 2717, 7330, 3, 2718, 7331, 4),
(2832, 'SIC', 4310, 50, 1, 3724, 5030, 3),
(2833, 'NAICS', 931, 423, 2, 1014, 42399, 4),
(2834, 'SIC', 4309, 40, 1, 3684, 4820, 3),
(2835, 'NAICS', 1766, 5616, 3, 1767, 56161, 4),
(2836, 'SEC', 2791, 20, 1, 2319, 2800, 2),
(2837, 'NAICS', 1015, 424, 2, 1073, 42481, 4),
(2838, 'SEC', 2219, 1220, 3, 2220, 1221, 4),
(2839, 'SIC', 4087, 7520, 3, 4088, 7521, 4),
(2840, 'SIC', 3507, 3660, 3, 3510, 3669, 4),
(2841, 'SIC', 3774, 5140, 3, 3782, 5148, 4),
(2842, 'SIC', 3822, 5400, 2, 3830, 5441, 4),
(2843, 'NAICS', 1851, 621, 2, 1885, 6216, 3),
(2844, 'SIC', 2901, 1200, 2, 2904, 1222, 4),
(2845, 'NAICS', 1812, 61, 1, 1843, 61169, 4),
(2846, 'SIC', 4311, 52, 1, 3904, 5961, 4),
(2847, 'SEC', 2788, 1, 1, 2214, 900, 2),
(2848, 'SEC', 2526, 4500, 2, 2530, 4520, 3),
(2849, 'SIC', 3208, 2780, 3, 3209, 2782, 4),
(2850, 'NAICS', 955, 4234, 3, 962, 423440, 5),
(2851, 'SIC', 4208, 8600, 2, 4216, 8641, 4),
(2852, 'SIC', 3818, 5330, 3, 3819, 5331, 4),
(2853, 'NAICS', 1015, 424, 2, 1029, 424320, 5),
(2854, 'NAICS', 1582, 53121, 4, 1581, 531210, 5),
(2855, 'SEC', 4320, 6170, 3, 4340, 6172, 4),
(2856, 'NAICS', 2003, 72, 1, 2035, 722514, 5),
(2857, 'SIC', 4308, 20, 1, 3041, 2100, 2),
(2858, 'SIC', 3371, 3400, 2, 3386, 3442, 4),
(2859, 'SIC', 3715, 5000, 2, 3761, 5099, 4),
(2860, 'SEC', 2704, 6790, 3, 4328, 6795, 4),
(2861, 'SIC', 3715, 5000, 2, 3731, 5044, 4),
(2862, 'NAICS', 1, 11, 1, 55, 111998, 5),
(2863, 'NAICS', 253, 2382, 3, 256, 238220, 5),
(2864, 'NAICS', 1403, 511, 2, 1404, 5111, 3),
(2865, 'SIC', 4307, 15, 1, 2963, 1741, 4),
(2866, 'SIC', 4309, 40, 1, 3646, 4481, 4),
(2867, 'SEC', 2794, 52, 1, 2623, 5600, 2),
(2868, 'NAICS', 56, 112, 2, 86, 112511, 5),
(2869, 'NAICS', 1015, 424, 2, 1017, 424110, 5),
(2870, 'NAICS', 1569, 53, 1, 1585, 531311, 5),
(2871, 'SEC', 2738, 7800, 2, 2745, 7830, 3),
(2872, 'NAICS', 1625, 541, 2, 1648, 54134, 4),
(2873, 'SEC', 2725, 7370, 3, 2729, 7374, 4),
(2874, 'NAICS', 1813, 611, 2, 1820, 6113, 3),
(2875, 'SIC', 2993, 2030, 3, 2994, 2032, 4),
(2876, 'SIC', 4308, 20, 1, 3161, 2540, 3),
(2877, 'SEC', 2796, 70, 1, 2739, 7810, 3),
(2878, 'SIC', 3419, 3500, 2, 3441, 3547, 4),
(2879, 'SIC', 4308, 20, 1, 3061, 2252, 4),
(2880, 'SIC', 3108, 2380, 3, 3113, 2387, 4),
(2881, 'NAICS', 1850, 62, 1, 1915, 623311, 5),
(2882, 'SIC', 3540, 3740, 3, 3541, 3743, 4),
(2883, 'NAICS', 977, 42361, 4, 976, 423610, 5),
(2884, 'NAICS', 1969, 712, 2, 1978, 71219, 4),
(2885, 'SIC', 3301, 3200, 2, 3322, 3270, 3),
(2886, 'SIC', 3680, 4800, 2, 3686, 4830, 3),
(2887, 'SIC', 4309, 40, 1, 3636, 4400, 2),
(2888, 'SIC', 2982, 2000, 2, 2993, 2030, 3),
(2889, 'SIC', 3762, 5100, 2, 3792, 5171, 4),
(2890, 'NAICS', 157, 21231, 4, 159, 212312, 5),
(2891, 'NAICS', 2038, 811, 2, 2056, 811213, 5),
(2892, 'NAICS', 1066, 4247, 3, 1068, 42471, 4),
(2893, 'NAICS', 1726, 561, 2, 1743, 56141, 4),
(2894, 'NAICS', 1, 11, 1, 38, 111411, 5),
(2895, 'SEC', 2240, 2000, 2, 2255, 2082, 4),
(2896, 'SEC', 2384, 3400, 2, 2399, 3460, 3),
(2897, 'SIC', 3059, 2250, 3, 3063, 2254, 4),
(2898, 'NAICS', 2135, 92, 1, 2156, 922130, 5),
(2899, 'SEC', 2795, 60, 1, 4326, 6532, 3),
(2900, 'NAICS', 1984, 71312, 4, 1983, 713120, 5),
(2901, 'NAICS', 1462, 5179, 3, 1465, 517919, 5),
(2902, 'SIC', 3480, 3600, 2, 3499, 3644, 4),
(2903, 'SIC', 4308, 20, 1, 3427, 3531, 4),
(2904, 'SIC', 2861, 760, 3, 2863, 762, 4),
(2905, 'NAICS', 138, 212, 2, 161, 212319, 5),
(2906, 'SEC', 2713, 7300, 2, 2721, 7359, 4),
(2907, 'SIC', 2825, 200, 2, 2837, 253, 4),
(2908, 'SIC', 4314, 90, 1, 4278, 9510, 3),
(2909, 'SIC', 3371, 3400, 2, 3390, 3448, 4),
(2910, 'SIC', 3854, 5600, 2, 3864, 5651, 4),
(2911, 'SIC', 4190, 8290, 3, 4191, 8299, 4),
(2912, 'SIC', 3301, 3200, 2, 3323, 3271, 4),
(2913, 'SIC', 4065, 7370, 3, 4070, 7375, 4),
(2914, 'SIC', 4308, 20, 1, 3443, 3549, 4),
(2915, 'NAICS', 218, 237, 2, 223, 23712, 4),
(2916, 'SEC', 2536, 4700, 2, 2537, 4730, 3),
(2917, 'SIC', 4215, 8640, 3, 4216, 8641, 4),
(2918, 'SIC', 4308, 20, 1, 3530, 3714, 4),
(2919, 'SIC', 3148, 2500, 2, 3159, 2530, 3),
(2920, 'SEC', 2791, 20, 1, 2290, 2540, 3),
(2921, 'SIC', 3261, 3000, 2, 3267, 3052, 4),
(2922, 'SEC', 2791, 20, 1, 2258, 2092, 4),
(2923, 'SIC', 3774, 5140, 3, 3776, 5142, 4),
(2924, 'NAICS', 1625, 541, 2, 1688, 54172, 4),
(2925, 'SIC', 4313, 70, 1, 4211, 8620, 3),
(2926, 'NAICS', 132, 21, 1, 157, 21231, 4),
(2927, 'NAICS', 138, 212, 2, 166, 212325, 5),
(2928, 'NAICS', 1942, 71, 1, 1944, 7111, 3),
(2929, 'SIC', 4040, 7300, 2, 4046, 7320, 3),
(2930, 'NAICS', 205, 23, 1, 211, 236117, 5),
(2931, 'NAICS', 218, 237, 2, 231, 23731, 4),
(2932, 'NAICS', 2013, 7212, 3, 2015, 721211, 5),
(2933, 'SEC', 2434, 3600, 2, 2454, 3678, 4),
(2934, 'NAICS', 982, 4237, 3, 988, 42373, 4),
(2935, 'SEC', 2302, 2700, 2, 2305, 2720, 3),
(2936, 'NAICS', 2141, 92112, 4, 2140, 921120, 5),
(2937, 'NAICS', 1785, 5619, 3, 1788, 561920, 5),
(2938, 'SIC', 3148, 2500, 2, 3154, 2517, 4),
(2939, 'SIC', 4312, 60, 1, 3966, 6350, 3),
(2940, 'NAICS', 1985, 7132, 3, 1987, 71321, 4),
(2941, 'SIC', 3050, 2200, 2, 3066, 2259, 4),
(2942, 'SIC', 4310, 50, 1, 3733, 5046, 4),
(2943, 'SIC', 3636, 4400, 2, 3645, 4480, 3),
(2944, 'SIC', 4040, 7300, 2, 4073, 7378, 4),
(2945, 'SEC', 2302, 2700, 2, 2312, 2750, 3),
(2946, 'SIC', 3886, 5900, 2, 3907, 5980, 3),
(2947, 'SIC', 3921, 6020, 3, 3923, 6022, 4),
(2948, 'NAICS', 2103, 813, 2, 2126, 81393, 4),
(2949, 'SEC', 2792, 40, 1, 2556, 4922, 4),
(2950, 'SIC', 4308, 20, 1, 3146, 2493, 4),
(2951, 'NAICS', 1569, 53, 1, 1616, 532420, 5),
(2952, 'NAICS', 1, 11, 1, 109, 1141, 3),
(2953, 'NAICS', 1794, 56211, 4, 1796, 562112, 5),
(2954, 'NAICS', 2187, 92512, 4, 2186, 925120, 5),
(2955, 'SIC', 3662, 4600, 2, 3665, 4613, 4),
(2956, 'SIC', 4313, 70, 1, 4160, 8052, 4),
(2957, 'SIC', 4307, 15, 1, 2948, 1600, 2),
(2958, 'SIC', 4313, 70, 1, 4042, 7311, 4),
(2959, 'NAICS', 144, 2122, 3, 147, 21222, 4),
(2960, 'SEC', 2667, 6160, 3, 2668, 6162, 4),
(2961, 'SIC', 4081, 7500, 2, 4083, 7513, 4),
(2962, 'NAICS', 36, 1114, 3, 38, 111411, 5),
(2963, 'NAICS', 2103, 813, 2, 2113, 81331, 4),
(2964, 'SIC', 4314, 90, 1, 4276, 9451, 4),
(2965, 'SIC', 4308, 20, 1, 3545, 3761, 4),
(2966, 'NAICS', 2103, 813, 2, 2115, 813312, 5),
(2967, 'SEC', 2791, 20, 1, 2433, 3590, 3),
(2968, 'SIC', 2907, 1240, 3, 2908, 1241, 4),
(2969, 'NAICS', 2181, 92412, 4, 2180, 924120, 5),
(2970, 'SIC', 4313, 70, 1, 4158, 8050, 3),
(2971, 'NAICS', 181, 221, 2, 185, 221112, 5),
(2972, 'NAICS', 2120, 8139, 3, 2122, 81391, 4),
(2973, 'SEC', 2526, 4500, 2, 2529, 4513, 4),
(2974, 'SEC', 2458, 3700, 2, 2471, 3743, 4),
(2975, 'SIC', 3316, 3260, 3, 3320, 3264, 4),
(2976, 'SIC', 3886, 5900, 2, 3887, 5910, 3),
(2977, 'SEC', 2664, 6150, 3, 2666, 6159, 4),
(2978, 'NAICS', 2038, 811, 2, 2054, 811211, 5),
(2979, 'NAICS', 2166, 923, 2, 2173, 92313, 4),
(2980, 'SIC', 3371, 3400, 2, 3396, 3462, 4),
(2981, 'SIC', 3337, 3300, 2, 3343, 3317, 4),
(2982, 'NAICS', 1813, 611, 2, 1828, 611430, 5),
(2983, 'SEC', 2434, 3600, 2, 2446, 3660, 3),
(2984, 'SIC', 4309, 40, 1, 3655, 4510, 3),
(2985, 'SIC', 3654, 4500, 2, 3655, 4510, 3),
(2986, 'NAICS', 2039, 8111, 3, 2046, 811121, 5),
(2987, 'SEC', 2659, 6100, 2, 4322, 6180, 3),
(2988, 'SIC', 4308, 20, 1, 3458, 3567, 4),
(2989, 'SIC', 3886, 5900, 2, 3909, 5984, 4),
(2990, 'NAICS', 202, 22132, 4, 201, 221320, 5),
(2991, 'SIC', 2798, 100, 2, 2800, 111, 4),
(2992, 'NAICS', 273, 2389, 3, 275, 23891, 4),
(2993, 'SIC', 4313, 70, 1, 4061, 7359, 4),
(2994, 'SIC', 3252, 2900, 2, 3256, 2951, 4),
(2995, 'SIC', 3576, 3900, 2, 3595, 3990, 3),
(2996, 'NAICS', 173, 2131, 3, 174, 21311, 4),
(2997, 'SEC', 2476, 3800, 2, 2498, 3870, 3),
(2998, 'SIC', 3282, 3100, 2, 3300, 3199, 4),
(2999, 'SIC', 3301, 3200, 2, 3319, 3263, 4),
(3000, 'NAICS', 1569, 53, 1, 1608, 532299, 5),
(3001, 'NAICS', 1441, 51229, 4, 1440, 512290, 5),
(3002, 'NAICS', 1480, 52, 1, 1553, 524298, 5),
(3003, 'SIC', 4146, 8000, 2, 4167, 8071, 4),
(3004, 'SIC', 4311, 52, 1, 3864, 5651, 4),
(3005, 'NAICS', 218, 237, 2, 224, 237130, 5),
(3006, 'NAICS', 1420, 5121, 3, 1429, 512191, 5),
(3007, 'SIC', 3020, 2070, 3, 3024, 2077, 4),
(3008, 'NAICS', 1741, 5614, 3, 1742, 561410, 5),
(3009, 'NAICS', 2037, 81, 1, 2103, 813, 2),
(3010, 'SEC', 2355, 3200, 2, 2366, 3270, 3),
(3011, 'SEC', 2450, 3670, 3, 2455, 3679, 4),
(3012, 'NAICS', 57, 1121, 3, 63, 112130, 5),
(3013, 'SIC', 4247, 9100, 2, 4250, 9120, 3),
(3014, 'NAICS', 1, 11, 1, 131, 11531, 4),
(3015, 'SEC', 2791, 20, 1, 2446, 3660, 3),
(3016, 'SEC', 2523, 4400, 2, 2525, 4412, 4),
(3017, 'SEC', 2791, 20, 1, 2242, 2011, 4),
(3018, 'SIC', 4308, 20, 1, 3479, 3599, 4),
(3019, 'NAICS', 1804, 5629, 3, 1810, 562991, 5),
(3020, 'SIC', 4308, 20, 1, 3034, 2091, 4),
(3021, 'NAICS', 1624, 54, 1, 1662, 541430, 5),
(3022, 'SIC', 3975, 6410, 3, 3976, 6411, 4),
(3023, 'NAICS', 1569, 53, 1, 1619, 53249, 4),
(3024, 'SIC', 3555, 3820, 3, 3562, 3827, 4),
(3025, 'SIC', 4308, 20, 1, 3249, 2893, 4),
(3026, 'SIC', 4040, 7300, 2, 4076, 7381, 4),
(3027, 'SIC', 2875, 900, 2, 2882, 970, 3),
(3028, 'NAICS', 174, 21311, 4, 177, 213113, 5),
(3029, 'SEC', 2378, 3340, 3, 2379, 3341, 4),
(3030, 'SIC', 4308, 20, 1, 3496, 3640, 3),
(3031, 'NAICS', 931, 423, 2, 983, 423710, 5),
(3032, 'SIC', 4308, 20, 1, 3521, 3691, 4),
(3033, 'SIC', 4308, 20, 1, 3237, 2860, 3),
(3034, 'SIC', 4308, 20, 1, 3379, 3429, 4),
(3035, 'SIC', 4313, 70, 1, 4011, 7021, 4),
(3036, 'SIC', 3026, 2080, 3, 3029, 2084, 4),
(3037, 'SEC', 2791, 20, 1, 2454, 3678, 4),
(3038, 'SEC', 2568, 5000, 2, 2581, 5064, 4),
(3039, 'SIC', 4308, 20, 1, 3065, 2258, 4),
(3040, 'SIC', 4242, 8810, 3, 4243, 8811, 4),
(3041, 'NAICS', 140, 21211, 4, 143, 212113, 5),
(3042, 'NAICS', 167, 21239, 4, 171, 212399, 5),
(3043, 'NAICS', 1413, 51119, 4, 1415, 511199, 5),
(3044, 'NAICS', 1419, 512, 2, 1424, 51212, 4),
(3045, 'SIC', 2864, 780, 3, 2867, 783, 4),
(3046, 'NAICS', 116, 11421, 4, 115, 114210, 5),
(3047, 'SEC', 2791, 20, 1, 2463, 3715, 4),
(3048, 'SIC', 2918, 1400, 2, 2922, 1422, 4),
(3049, 'SIC', 4308, 20, 1, 3432, 3536, 4),
(3050, 'NAICS', 1709, 54192, 4, 1710, 541921, 5),
(3051, 'SIC', 4311, 52, 1, 3843, 5531, 4),
(3052, 'NAICS', 1624, 54, 1, 1705, 54189, 4),
(3053, 'SEC', 2797, 90, 1, 2785, 9700, 2),
(3054, 'SIC', 3241, 2870, 3, 3243, 2874, 4),
(3055, 'SIC', 4313, 70, 1, 4215, 8640, 3),
(3056, 'SIC', 2847, 700, 2, 2867, 783, 4),
(3057, 'NAICS', 79, 1124, 3, 80, 112410, 5),
(3058, 'SIC', 3149, 2510, 3, 3150, 2511, 4),
(3059, 'SEC', 2591, 5100, 2, 2602, 5172, 4),
(3060, 'NAICS', 1569, 53, 1, 1604, 53223, 4),
(3061, 'SEC', 2796, 70, 1, 2772, 8351, 4),
(3062, 'NAICS', 68, 1123, 3, 69, 112310, 5),
(3063, 'NAICS', 1402, 51, 1, 1477, 51913, 4),
(3064, 'SIC', 4305, 1, 1, 2827, 211, 4),
(3065, 'NAICS', 1744, 56142, 4, 1745, 561421, 5),
(3066, 'SIC', 4308, 20, 1, 3033, 2090, 3),
(3067, 'SIC', 3937, 6100, 2, 3943, 6153, 4),
(3068, 'NAICS', 1569, 53, 1, 1589, 531390, 5),
(3069, 'SIC', 4230, 8730, 3, 4232, 8732, 4),
(3070, 'SIC', 4162, 8060, 3, 4165, 8069, 4),
(3071, 'NAICS', 1490, 52212, 4, 1489, 522120, 5),
(3072, 'NAICS', 172, 213, 2, 178, 213114, 5),
(3073, 'NAICS', 1625, 541, 2, 1635, 54121, 4),
(3074, 'NAICS', 1625, 541, 2, 1710, 541921, 5),
(3075, 'SIC', 4306, 10, 1, 2921, 1420, 3),
(3076, 'SIC', 3762, 5100, 2, 3779, 5145, 4),
(3077, 'SIC', 4313, 70, 1, 4062, 7360, 3),
(3078, 'SEC', 2795, 60, 1, 2667, 6160, 3),
(3079, 'NAICS', 1485, 522, 2, 1511, 522390, 5),
(3080, 'SIC', 4311, 52, 1, 3829, 5440, 3),
(3081, 'SIC', 3693, 4900, 2, 3704, 4939, 4),
(3082, 'NAICS', 1741, 5614, 3, 1749, 561439, 5),
(3083, 'SIC', 4309, 40, 1, 3617, 4151, 4),
(3084, 'NAICS', 64, 11213, 4, 63, 112130, 5),
(3085, 'NAICS', 253, 2382, 3, 255, 23821, 4),
(3086, 'NAICS', 930, 42, 1, 1079, 424920, 5),
(3087, 'SIC', 2918, 1400, 2, 2929, 1455, 4),
(3088, 'NAICS', 1908, 6232, 3, 1912, 62322, 4),
(3089, 'SIC', 4313, 70, 1, 4106, 7631, 4),
(3090, 'NAICS', 180, 22, 1, 196, 221210, 5),
(3091, 'NAICS', 2003, 72, 1, 2034, 722513, 5),
(3092, 'SIC', 4310, 50, 1, 3775, 5141, 4),
(3093, 'NAICS', 1402, 51, 1, 1419, 512, 2),
(3094, 'SEC', 2459, 3710, 3, 2461, 3713, 4),
(3095, 'SIC', 4002, 6790, 3, 4006, 6799, 4),
(3096, 'SEC', 2403, 3500, 2, 2433, 3590, 3),
(3097, 'SEC', 2780, 8740, 3, 2783, 8744, 4),
(3098, 'NAICS', 1792, 562, 2, 1808, 56292, 4),
(3099, 'SIC', 3344, 3320, 3, 3347, 3324, 4),
(3100, 'SEC', 2552, 4900, 2, 2566, 4960, 3),
(3101, 'SIC', 3124, 2400, 2, 3128, 2421, 4),
(3102, 'NAICS', 2020, 722, 2, 2025, 72232, 4),
(3103, 'NAICS', 1856, 6212, 3, 1857, 621210, 5),
(3104, 'SEC', 2792, 40, 1, 2526, 4500, 2),
(3105, 'NAICS', 1895, 6221, 3, 1896, 622110, 5),
(3106, 'NAICS', 1089, 425, 2, 1092, 42511, 4),
(3107, 'NAICS', 1766, 5616, 3, 1769, 561612, 5),
(3108, 'SIC', 3409, 3490, 3, 3415, 3496, 4),
(3109, 'NAICS', 1026, 4243, 3, 1034, 42434, 4),
(3110, 'NAICS', 1625, 541, 2, 1634, 5412, 3),
(3111, 'NAICS', 1901, 6223, 3, 1903, 62231, 4),
(3112, 'SIC', 4305, 1, 1, 2855, 740, 3),
(3113, 'NAICS', 1625, 541, 2, 1683, 5417, 3),
(3114, 'SEC', 2234, 1600, 2, 2236, 1623, 4),
(3115, 'NAICS', 930, 42, 1, 958, 423420, 5),
(3116, 'NAICS', 1785, 5619, 3, 1786, 561910, 5),
(3117, 'SIC', 4308, 20, 1, 3029, 2084, 4),
(3118, 'SIC', 2847, 700, 2, 2865, 781, 4),
(3119, 'NAICS', 1555, 5251, 3, 1560, 525190, 5),
(3120, 'NAICS', 1431, 5122, 3, 1441, 51229, 4),
(3121, 'NAICS', 2120, 8139, 3, 2124, 81392, 4),
(3122, 'SEC', 2262, 2200, 2, 2269, 2270, 3),
(3123, 'SIC', 2864, 780, 3, 2865, 781, 4),
(3124, 'SIC', 3480, 3600, 2, 3523, 3694, 4),
(3125, 'NAICS', 930, 42, 1, 979, 42362, 4),
(3126, 'NAICS', 930, 42, 1, 1021, 424130, 5),
(3127, 'NAICS', 1470, 519, 2, 1472, 519110, 5),
(3128, 'SIC', 2982, 2000, 2, 3039, 2098, 4),
(3129, 'SIC', 4308, 20, 1, 3572, 3860, 3),
(3130, 'SIC', 2847, 700, 2, 2857, 742, 4),
(3131, 'NAICS', 1943, 711, 2, 1951, 711190, 5),
(3132, 'SIC', 4308, 20, 1, 3048, 2140, 3),
(3133, 'SIC', 3337, 3300, 2, 3344, 3320, 3),
(3134, 'NAICS', 1942, 71, 1, 2000, 71395, 4),
(3135, 'NAICS', 1640, 5413, 3, 1644, 54132, 4),
(3136, 'SEC', 2424, 3570, 3, 2428, 3577, 4),
(3137, 'SIC', 3237, 2860, 3, 3238, 2861, 4),
(3138, 'NAICS', 1419, 512, 2, 1430, 512199, 5),
(3139, 'SIC', 3822, 5400, 2, 3824, 5411, 4),
(3140, 'NAICS', 2135, 92, 1, 2164, 922190, 5),
(3141, 'NAICS', 236, 2381, 3, 252, 23819, 4),
(3142, 'NAICS', 1071, 4248, 3, 1074, 424820, 5),
(3143, 'SEC', 2791, 20, 1, 2475, 3790, 3),
(3144, 'NAICS', 1942, 71, 1, 1999, 713950, 5),
(3145, 'SIC', 4312, 60, 1, 3989, 6550, 3),
(3146, 'SEC', 2703, 6700, 2, 4328, 6795, 4),
(3147, 'SIC', 4308, 20, 1, 3384, 3440, 3),
(3148, 'SIC', 4312, 60, 1, 3949, 6210, 3),
(3149, 'SEC', 2794, 52, 1, 2613, 5330, 3),
(3150, 'SIC', 2993, 2030, 3, 2996, 2034, 4),
(3151, 'SIC', 3715, 5000, 2, 3747, 5075, 4),
(3152, 'SIC', 3124, 2400, 2, 3142, 2451, 4),
(3153, 'SIC', 3496, 3640, 3, 3498, 3643, 4),
(3154, 'SIC', 3886, 5900, 2, 3913, 5993, 4),
(3155, 'NAICS', 2037, 81, 1, 2119, 81341, 4),
(3156, 'SIC', 2887, 1020, 3, 2888, 1021, 4),
(3157, 'NAICS', 1718, 55, 1, 1720, 5511, 3),
(3158, 'NAICS', 1726, 561, 2, 1760, 56151, 4),
(3159, 'SEC', 2610, 5300, 2, 2611, 5310, 3),
(3160, 'SIC', 4308, 20, 1, 3068, 2261, 4),
(3161, 'NAICS', 1920, 624, 2, 1931, 62422, 4),
(3162, 'SIC', 4268, 9400, 2, 4275, 9450, 3),
(3163, 'NAICS', 2, 111, 2, 34, 111336, 5),
(3164, 'SEC', 2789, 10, 1, 2217, 1090, 3),
(3165, 'NAICS', 1850, 62, 1, 1913, 6233, 3),
(3166, 'SEC', 2713, 7300, 2, 2725, 7370, 3),
(3167, 'SIC', 2955, 1700, 2, 2958, 1720, 3),
(3168, 'SIC', 3214, 2800, 2, 3215, 2810, 3),
(3169, 'SEC', 2794, 52, 1, 2632, 5712, 4),
(3170, 'SIC', 3050, 2200, 2, 3080, 2297, 4),
(3171, 'SIC', 4166, 8070, 3, 4167, 8071, 4),
(3172, 'NAICS', 56, 112, 2, 63, 112130, 5),
(3173, 'NAICS', 1431, 5122, 3, 1433, 51221, 4),
(3174, 'NAICS', 982, 4237, 3, 989, 423740, 5),
(3175, 'NAICS', 2020, 722, 2, 2033, 722511, 5),
(3176, 'SIC', 4309, 40, 1, 3661, 4581, 4),
(3177, 'SEC', 2276, 2400, 2, 2277, 2420, 3),
(3178, 'SIC', 4310, 50, 1, 3759, 5093, 4),
(3179, 'SIC', 4308, 20, 1, 3012, 2060, 3),
(3180, 'SIC', 4178, 8200, 2, 4183, 8222, 4),
(3181, 'SIC', 4081, 7500, 2, 4089, 7530, 3),
(3182, 'NAICS', 1954, 71121, 4, 1956, 711212, 5),
(3183, 'NAICS', 2135, 92, 1, 2168, 923110, 5),
(3184, 'SIC', 4313, 70, 1, 4182, 8221, 4),
(3185, 'NAICS', 2, 111, 2, 18, 111199, 5),
(3186, 'NAICS', 1513, 523, 2, 1525, 52321, 4),
(3187, 'SEC', 2371, 3300, 2, 2373, 3312, 4),
(3188, 'SIC', 4309, 40, 1, 3678, 4785, 4),
(3189, 'NAICS', 1, 11, 1, 25, 11131, 4),
(3190, 'SIC', 4308, 20, 1, 3203, 2759, 4),
(3191, 'SIC', 3911, 5990, 3, 3914, 5994, 4),
(3192, 'NAICS', 105, 1133, 3, 106, 113310, 5),
(3193, 'SEC', 2796, 70, 1, 2732, 7381, 4),
(3194, 'SIC', 4309, 40, 1, 3701, 4930, 3),
(3195, 'SIC', 3451, 3560, 3, 3452, 3561, 4),
(3196, 'NAICS', 104, 11321, 4, 103, 113210, 5),
(3197, 'SIC', 4313, 70, 1, 4119, 7829, 4),
(3198, 'NAICS', 1506, 5223, 3, 1510, 52232, 4),
(3199, 'NAICS', 1943, 711, 2, 1948, 71112, 4),
(3200, 'SIC', 3230, 2840, 3, 3231, 2841, 4),
(3201, 'NAICS', 1480, 52, 1, 1542, 524126, 5),
(3202, 'NAICS', 248, 23816, 4, 247, 238160, 5),
(3203, 'SEC', 2649, 6000, 2, 2653, 6029, 4),
(3204, 'NAICS', 930, 42, 1, 1082, 42493, 4),
(3205, 'NAICS', 2135, 92, 1, 2136, 921, 2),
(3206, 'SEC', 2579, 5060, 3, 2582, 5065, 4),
(3207, 'SEC', 2550, 4890, 3, 2551, 4899, 4),
(3208, 'SIC', 3461, 3570, 3, 3466, 3578, 4),
(3209, 'SEC', 2415, 3550, 3, 2417, 3559, 4),
(3210, 'NAICS', 132, 21, 1, 175, 213111, 5),
(3211, 'NAICS', 930, 42, 1, 1009, 423930, 5),
(3212, 'SEC', 2791, 20, 1, 2365, 3260, 3),
(3213, 'SIC', 3480, 3600, 2, 3481, 3610, 3),
(3214, 'NAICS', 1942, 71, 1, 1990, 7139, 3),
(3215, 'SIC', 4297, 9700, 2, 4300, 9720, 3),
(3216, 'NAICS', 2085, 8123, 3, 2089, 81232, 4),
(3217, 'SIC', 3077, 2290, 3, 3079, 2296, 4),
(3218, 'NAICS', 2038, 811, 2, 2045, 81112, 4),
(3219, 'NAICS', 1485, 522, 2, 1504, 522294, 5),
(3220, 'NAICS', 1851, 621, 2, 1854, 621111, 5),
(3221, 'SEC', 2267, 2250, 3, 2268, 2253, 4),
(3222, 'NAICS', 1480, 52, 1, 1551, 524291, 5),
(3223, 'NAICS', 1672, 5416, 3, 1674, 541611, 5),
(3224, 'NAICS', 1813, 611, 2, 1824, 611410, 5),
(3225, 'SIC', 4017, 7200, 2, 4018, 7210, 3),
(3226, 'SIC', 2799, 110, 3, 2800, 111, 4),
(3227, 'NAICS', 1480, 52, 1, 1536, 524, 2),
(3228, 'NAICS', 1942, 71, 1, 1996, 71393, 4),
(3229, 'SIC', 3636, 4400, 2, 3648, 4489, 4),
(3230, 'SIC', 4310, 50, 1, 3777, 5143, 4),
(3231, 'SEC', 2408, 3530, 3, 2411, 3533, 4),
(3232, 'SEC', 2792, 40, 1, 2540, 4810, 3),
(3233, 'SEC', 2677, 6300, 2, 2678, 6310, 3),
(3234, 'SIC', 3958, 6300, 2, 3965, 6331, 4),
(3235, 'SEC', 2791, 20, 1, 2340, 2950, 3),
(3236, 'SIC', 4308, 20, 1, 2992, 2026, 4),
(3237, 'NAICS', 1480, 52, 1, 1546, 52413, 4),
(3238, 'NAICS', 1905, 6231, 3, 1907, 62311, 4),
(3239, 'SIC', 3190, 2700, 2, 3203, 2759, 4),
(3240, 'SIC', 3854, 5600, 2, 3865, 5660, 3),
(3241, 'SIC', 3992, 6700, 2, 4006, 6799, 4),
(3242, 'SIC', 3715, 5000, 2, 3751, 5083, 4),
(3243, 'SIC', 2982, 2000, 2, 2991, 2024, 4),
(3244, 'NAICS', 1673, 54161, 4, 1678, 541618, 5),
(3245, 'NAICS', 2007, 72111, 4, 2006, 721110, 5),
(3246, 'SIC', 4049, 7330, 3, 4053, 7336, 4),
(3247, 'SEC', 2794, 52, 1, 2639, 5812, 4),
(3248, 'SIC', 2982, 2000, 2, 3003, 2044, 4),
(3249, 'SIC', 3008, 2050, 3, 3010, 2052, 4),
(3250, 'SIC', 3330, 3290, 3, 3336, 3299, 4),
(3251, 'SIC', 4017, 7200, 2, 4038, 7291, 4),
(3252, 'NAICS', 1537, 5241, 3, 1538, 52411, 4),
(3253, 'SIC', 4230, 8730, 3, 4231, 8731, 4),
(3254, 'SIC', 3553, 3810, 3, 3554, 3812, 4),
(3255, 'SIC', 4040, 7300, 2, 4069, 7374, 4),
(3256, 'SEC', 2791, 20, 1, 2315, 2770, 3),
(3257, 'NAICS', 931, 423, 2, 957, 42341, 4),
(3258, 'SEC', 2384, 3400, 2, 2392, 3442, 4),
(3259, 'NAICS', 235, 238, 2, 239, 238120, 5),
(3260, 'NAICS', 260, 2383, 3, 269, 238350, 5),
(3261, 'NAICS', 2003, 72, 1, 2018, 721310, 5),
(3262, 'SIC', 4308, 20, 1, 3082, 2299, 4),
(3263, 'NAICS', 1402, 51, 1, 1478, 519190, 5),
(3264, 'SEC', 2796, 70, 1, 2723, 7361, 4),
(3265, 'SEC', 2434, 3600, 2, 2435, 3610, 3),
(3266, 'SIC', 2825, 200, 2, 2835, 251, 4),
(3267, 'NAICS', 2185, 92511, 4, 2184, 925110, 5),
(3268, 'SIC', 3148, 2500, 2, 3149, 2510, 3),
(3269, 'NAICS', 2, 111, 2, 52, 11199, 4),
(3270, 'NAICS', 1938, 62431, 4, 1937, 624310, 5),
(3271, 'SIC', 3846, 5550, 3, 3847, 5551, 4),
(3272, 'SIC', 3041, 2100, 2, 3047, 2131, 4),
(3273, 'NAICS', 260, 2383, 3, 267, 238340, 5),
(3274, 'NAICS', 1569, 53, 1, 1586, 531312, 5),
(3275, 'SIC', 3167, 2600, 2, 3176, 2653, 4),
(3276, 'NAICS', 23, 1113, 3, 25, 11131, 4),
(3277, 'NAICS', 959, 42342, 4, 958, 423420, 5),
(3278, 'SIC', 4109, 7690, 3, 4111, 7694, 4),
(3279, 'NAICS', 1726, 561, 2, 1791, 56199, 4),
(3280, 'NAICS', 167, 21239, 4, 169, 212392, 5),
(3281, 'NAICS', 1628, 54111, 4, 1627, 541110, 5),
(3282, 'SEC', 2568, 5000, 2, 2583, 5070, 3),
(3283, 'NAICS', 1813, 611, 2, 1834, 611513, 5),
(3284, 'SEC', 2774, 8700, 2, 2780, 8740, 3),
(3285, 'SIC', 4311, 52, 1, 3845, 5541, 4),
(3286, 'SIC', 3301, 3200, 2, 3335, 3297, 4),
(3287, 'NAICS', 1495, 5222, 3, 1505, 522298, 5),
(3288, 'SIC', 3124, 2400, 2, 3140, 2449, 4),
(3289, 'NAICS', 930, 42, 1, 1083, 424940, 5),
(3290, 'SIC', 4308, 20, 1, 3027, 2082, 4),
(3291, 'NAICS', 1562, 5259, 3, 1564, 52591, 4),
(3292, 'NAICS', 2137, 9211, 3, 2144, 921140, 5),
(3293, 'SIC', 4313, 70, 1, 4153, 8040, 3),
(3294, 'SIC', 3344, 3320, 3, 3345, 3321, 4),
(3295, 'NAICS', 930, 42, 1, 984, 42371, 4),
(3296, 'SIC', 4308, 20, 1, 3598, 3995, 4),
(3297, 'NAICS', 1612, 5324, 3, 1613, 53241, 4),
(3298, 'SIC', 3526, 3700, 2, 3538, 3731, 4),
(3299, 'SIC', 3372, 3410, 3, 3374, 3412, 4),
(3300, 'SEC', 2319, 2800, 2, 2320, 2810, 3),
(3301, 'NAICS', 1554, 525, 2, 1561, 52519, 4),
(3302, 'NAICS', 1792, 562, 2, 1805, 562910, 5),
(3303, 'SEC', 2628, 5660, 3, 2629, 5661, 4),
(3304, 'SIC', 3419, 3500, 2, 3430, 3534, 4),
(3305, 'SIC', 2869, 810, 3, 2870, 811, 4),
(3306, 'SIC', 2845, 290, 3, 2846, 291, 4),
(3307, 'SEC', 2791, 20, 1, 2435, 3610, 3),
(3308, 'NAICS', 108, 114, 2, 112, 114112, 5),
(3309, 'NAICS', 1979, 713, 2, 1992, 71391, 4),
(3310, 'SEC', 2240, 2000, 2, 2251, 2052, 4),
(3311, 'SIC', 4305, 1, 1, 2844, 279, 4),
(3312, 'NAICS', 2120, 8139, 3, 2121, 813910, 5),
(3313, 'SIC', 2825, 200, 2, 2834, 250, 3),
(3314, 'SIC', 4313, 70, 1, 4091, 7533, 4),
(3315, 'NAICS', 235, 238, 2, 266, 23833, 4),
(3316, 'SIC', 3807, 5230, 3, 3808, 5231, 4),
(3317, 'NAICS', 2150, 922, 2, 2159, 92214, 4),
(3318, 'SIC', 3552, 3800, 2, 3559, 3824, 4),
(3319, 'SIC', 3083, 2300, 2, 3116, 2391, 4),
(3320, 'SIC', 3434, 3540, 3, 3438, 3544, 4),
(3321, 'NAICS', 1003, 42386, 4, 1002, 423860, 5),
(3322, 'NAICS', 205, 23, 1, 234, 23799, 4),
(3323, 'SIC', 2955, 1700, 2, 2968, 1752, 4),
(3324, 'SIC', 3083, 2300, 2, 3088, 2322, 4),
(3325, 'SIC', 4125, 7900, 2, 4139, 7990, 3),
(3326, 'NAICS', 56, 112, 2, 87, 112512, 5),
(3327, 'NAICS', 156, 2123, 3, 166, 212325, 5),
(3328, 'SIC', 3050, 2200, 2, 3063, 2254, 4),
(3329, 'SIC', 3762, 5100, 2, 3768, 5122, 4),
(3330, 'NAICS', 1480, 52, 1, 1541, 52412, 4),
(3331, 'NAICS', 1402, 51, 1, 1451, 51521, 4),
(3332, 'NAICS', 1625, 541, 2, 1645, 541330, 5),
(3333, 'SIC', 3576, 3900, 2, 3580, 3915, 4),
(3334, 'NAICS', 1452, 517, 2, 1465, 517919, 5),
(3335, 'SIC', 4308, 20, 1, 3491, 3632, 4),
(3336, 'NAICS', 1619, 53249, 4, 1618, 532490, 5),
(3337, 'SEC', 2795, 60, 1, 2663, 6141, 4),
(3338, 'SIC', 4176, 8110, 3, 4177, 8111, 4),
(3339, 'NAICS', 1624, 54, 1, 1663, 54143, 4),
(3340, 'SIC', 3050, 2200, 2, 3051, 2210, 3),
(3341, 'SEC', 2794, 52, 1, 2647, 5961, 4),
(3342, 'SIC', 4017, 7200, 2, 4036, 7261, 4),
(3343, 'NAICS', 2, 111, 2, 39, 111419, 5),
(3344, 'NAICS', 1725, 56, 1, 1756, 561492, 5),
(3345, 'NAICS', 2093, 8129, 3, 2099, 812930, 5),
(3346, 'SEC', 2640, 5900, 2, 2644, 5944, 4),
(3347, 'SEC', 2795, 60, 1, 2657, 6090, 3),
(3348, 'SEC', 2796, 70, 1, 2754, 8010, 3),
(3349, 'SIC', 4311, 52, 1, 3865, 5660, 3),
(3350, 'SIC', 4291, 9640, 3, 4292, 9641, 4),
(3351, 'NAICS', 2103, 813, 2, 2125, 813930, 5),
(3352, 'NAICS', 2039, 8111, 3, 2042, 811112, 5),
(3353, 'NAICS', 1958, 7113, 3, 1959, 711310, 5),
(3354, 'NAICS', 25, 11131, 4, 24, 111310, 5),
(3355, 'SEC', 2292, 2600, 2, 2300, 2670, 3),
(3356, 'SEC', 2791, 20, 1, 2465, 3720, 3),
(3357, 'SIC', 4308, 20, 1, 3492, 3633, 4),
(3358, 'SIC', 4309, 40, 1, 3675, 4741, 4),
(3359, 'SIC', 3749, 5080, 3, 3754, 5087, 4),
(3360, 'SEC', 2458, 3700, 2, 2460, 3711, 4),
(3361, 'SIC', 3337, 3300, 2, 3346, 3322, 4),
(3362, 'SEC', 2793, 50, 1, 2584, 5072, 4),
(3363, 'SIC', 4313, 70, 1, 4095, 7538, 4),
(3364, 'SIC', 3059, 2250, 3, 3066, 2259, 4),
(3365, 'SIC', 3626, 4220, 3, 3629, 4225, 4),
(3366, 'SIC', 3837, 5500, 2, 3848, 5560, 3),
(3367, 'NAICS', 1402, 51, 1, 1449, 5152, 3),
(3368, 'NAICS', 1943, 711, 2, 1950, 71113, 4),
(3369, 'SIC', 3355, 3350, 3, 3359, 3355, 4),
(3370, 'SIC', 3496, 3640, 3, 3497, 3641, 4),
(3371, 'SIC', 3654, 4500, 2, 3661, 4581, 4),
(3372, 'SIC', 4314, 90, 1, 4267, 9311, 4),
(3373, 'SIC', 3605, 4100, 2, 3616, 4150, 3),
(3374, 'SIC', 3026, 2080, 3, 3027, 2082, 4),
(3375, 'SIC', 3576, 3900, 2, 3583, 3940, 3),
(3376, 'SIC', 4075, 7380, 3, 4076, 7381, 4),
(3377, 'SEC', 2623, 5600, 2, 2627, 5651, 4),
(3378, 'NAICS', 1631, 54119, 4, 1633, 541199, 5),
(3379, 'SIC', 4312, 60, 1, 3924, 6029, 4),
(3380, 'NAICS', 988, 42373, 4, 987, 423730, 5),
(3381, 'NAICS', 2167, 9231, 3, 2170, 923120, 5),
(3382, 'SEC', 2292, 2600, 2, 2293, 2610, 3),
(3383, 'SEC', 2240, 2000, 2, 2241, 2010, 3),
(3384, 'SIC', 3426, 3530, 3, 3429, 3533, 4),
(3385, 'SEC', 2458, 3700, 2, 2472, 3750, 3),
(3386, 'SEC', 2591, 5100, 2, 2601, 5171, 4),
(3387, 'NAICS', 156, 2123, 3, 161, 212319, 5),
(3388, 'NAICS', 1485, 522, 2, 1497, 52221, 4),
(3389, 'SEC', 2796, 70, 1, 2766, 8100, 2),
(3390, 'SIC', 3552, 3800, 2, 3557, 3822, 4),
(3391, 'SIC', 3083, 2300, 2, 3104, 2361, 4),
(3392, 'SEC', 2254, 2080, 3, 2256, 2086, 4),
(3393, 'NAICS', 1554, 525, 2, 1556, 525110, 5),
(3394, 'SEC', 2795, 60, 1, 2708, 6799, 4),
(3395, 'SIC', 3693, 4900, 2, 3700, 4925, 4),
(3396, 'SIC', 4309, 40, 1, 3667, 4700, 2),
(3397, 'NAICS', 1913, 6233, 3, 1914, 62331, 4),
(3398, 'NAICS', 1850, 62, 1, 1853, 62111, 4),
(3399, 'SEC', 2659, 6100, 2, 2664, 6150, 3),
(3400, 'NAICS', 975, 4236, 3, 977, 42361, 4),
(3401, 'SIC', 2955, 1700, 2, 2979, 1795, 4),
(3402, 'SIC', 2955, 1700, 2, 2978, 1794, 4),
(3403, 'SIC', 3434, 3540, 3, 3440, 3546, 4),
(3404, 'NAICS', 1015, 424, 2, 1076, 4249, 3),
(3405, 'SIC', 4308, 20, 1, 3026, 2080, 3),
(3406, 'SIC', 4308, 20, 1, 3190, 2700, 2),
(3407, 'SIC', 3215, 2810, 3, 3218, 2816, 4),
(3408, 'SEC', 2792, 40, 1, 2536, 4700, 2),
(3409, 'SIC', 3791, 5170, 3, 3793, 5172, 4),
(3410, 'SIC', 3050, 2200, 2, 3077, 2290, 3),
(3411, 'NAICS', 1946, 71111, 4, 1945, 711110, 5),
(3412, 'SEC', 2231, 1530, 3, 2232, 1531, 4),
(3413, 'SIC', 3419, 3500, 2, 3435, 3541, 4),
(3414, 'SEC', 2476, 3800, 2, 2495, 3851, 4),
(3415, 'SIC', 3108, 2380, 3, 3114, 2389, 4),
(3416, 'SIC', 3784, 5150, 3, 3787, 5159, 4),
(3417, 'NAICS', 1741, 5614, 3, 1754, 56149, 4),
(3418, 'NAICS', 2188, 926, 2, 2192, 926120, 5),
(3419, 'NAICS', 930, 42, 1, 938, 42313, 4),
(3420, 'NAICS', 930, 42, 1, 1063, 42461, 4),
(3421, 'SIC', 3468, 3580, 3, 3471, 3585, 4),
(3422, 'SIC', 3696, 4920, 3, 3698, 4923, 4),
(3423, 'NAICS', 1851, 621, 2, 1872, 621410, 5),
(3424, 'SEC', 2534, 4600, 2, 2535, 4610, 3),
(3425, 'SIC', 4307, 15, 1, 2954, 1629, 4),
(3426, 'NAICS', 2037, 81, 1, 2109, 813211, 5),
(3427, 'NAICS', 2071, 812, 2, 2093, 8129, 3),
(3428, 'SIC', 3409, 3490, 3, 3412, 3493, 4),
(3429, 'NAICS', 1591, 532, 2, 1603, 532230, 5),
(3430, 'NAICS', 56, 112, 2, 70, 11231, 4),
(3431, 'NAICS', 228, 23721, 4, 227, 237210, 5),
(3432, 'SIC', 3749, 5080, 3, 3751, 5083, 4),
(3433, 'NAICS', 1526, 5239, 3, 1528, 52391, 4),
(3434, 'SEC', 2355, 3200, 2, 2359, 3221, 4),
(3435, 'SIC', 3481, 3610, 3, 3483, 3613, 4),
(3436, 'SIC', 4308, 20, 1, 3410, 3491, 4),
(3437, 'NAICS', 1452, 517, 2, 1460, 517410, 5),
(3438, 'NAICS', 1625, 541, 2, 1664, 541490, 5),
(3439, 'SIC', 4310, 50, 1, 3781, 5147, 4),
(3440, 'SEC', 2791, 20, 1, 2379, 3341, 4),
(3441, 'NAICS', 1850, 62, 1, 1934, 624230, 5),
(3442, 'SEC', 2794, 52, 1, 2622, 5531, 4),
(3443, 'NAICS', 930, 42, 1, 1091, 425110, 5),
(3444, 'NAICS', 1402, 51, 1, 1479, 51919, 4),
(3445, 'NAICS', 1555, 5251, 3, 1558, 525120, 5),
(3446, 'NAICS', 1673, 54161, 4, 1674, 541611, 5),
(3447, 'NAICS', 205, 23, 1, 251, 238190, 5),
(3448, 'NAICS', 1980, 7131, 3, 1983, 713120, 5),
(3449, 'NAICS', 2137, 9211, 3, 2139, 92111, 4),
(3450, 'NAICS', 132, 21, 1, 161, 212319, 5),
(3451, 'NAICS', 1569, 53, 1, 1615, 532412, 5),
(3452, 'SEC', 2476, 3800, 2, 2491, 3843, 4),
(3453, 'NAICS', 1015, 424, 2, 1021, 424130, 5),
(3454, 'NAICS', 2071, 812, 2, 2080, 8122, 3),
(3455, 'SEC', 2791, 20, 1, 2403, 3500, 2),
(3456, 'NAICS', 98, 113, 2, 104, 11321, 4),
(3457, 'SEC', 2659, 6100, 2, 2660, 6110, 3),
(3458, 'SIC', 4313, 70, 1, 4071, 7376, 4),
(3459, 'NAICS', 1850, 62, 1, 1887, 62161, 4),
(3460, 'SIC', 3693, 4900, 2, 3707, 4950, 3),
(3461, 'NAICS', 1506, 5223, 3, 1507, 522310, 5),
(3462, 'SIC', 3164, 2590, 3, 3166, 2599, 4),
(3463, 'SIC', 3696, 4920, 3, 3699, 4924, 4),
(3464, 'NAICS', 182, 2211, 3, 191, 221118, 5),
(3465, 'NAICS', 1485, 522, 2, 1493, 522190, 5),
(3466, 'SIC', 4314, 90, 1, 4260, 9221, 4),
(3467, 'SIC', 3893, 5940, 3, 3894, 5941, 4),
(3468, 'SIC', 3886, 5900, 2, 3893, 5940, 3),
(3469, 'NAICS', 1625, 541, 2, 1637, 541213, 5),
(3470, 'NAICS', 1888, 6219, 3, 1891, 62199, 4),
(3471, 'NAICS', 1659, 54141, 4, 1658, 541410, 5),
(3472, 'SEC', 2238, 1730, 3, 2239, 1731, 4),
(3473, 'SEC', 2791, 20, 1, 2250, 2050, 3),
(3474, 'SIC', 3945, 6160, 3, 3947, 6163, 4),
(3475, 'NAICS', 1402, 51, 1, 1437, 51223, 4),
(3476, 'SEC', 2793, 50, 1, 2589, 5094, 4),
(3477, 'NAICS', 195, 2212, 3, 196, 221210, 5),
(3478, 'NAICS', 207, 2361, 3, 212, 236118, 5),
(3479, 'SIC', 3419, 3500, 2, 3459, 3568, 4),
(3480, 'SIC', 4309, 40, 1, 3671, 4729, 4),
(3481, 'NAICS', 1624, 54, 1, 1659, 54141, 4),
(3482, 'SIC', 4308, 20, 1, 3242, 2873, 4),
(3483, 'SIC', 4311, 52, 1, 3818, 5330, 3),
(3484, 'SIC', 4313, 70, 1, 4226, 8712, 4),
(3485, 'NAICS', 1850, 62, 1, 1919, 62399, 4),
(3486, 'NAICS', 23, 1113, 3, 31, 111333, 5),
(3487, 'NAICS', 946, 4233, 3, 954, 42339, 4),
(3488, 'NAICS', 2135, 92, 1, 2185, 92511, 4),
(3489, 'SIC', 3576, 3900, 2, 3591, 3955, 4),
(3490, 'SEC', 2618, 5410, 3, 4319, 5412, 4),
(3491, 'SIC', 4308, 20, 1, 3408, 3489, 4),
(3492, 'SIC', 4305, 1, 1, 2826, 210, 3),
(3493, 'NAICS', 235, 238, 2, 274, 238910, 5),
(3494, 'NAICS', 2103, 813, 2, 2108, 81321, 4),
(3495, 'NAICS', 1965, 71141, 4, 1964, 711410, 5),
(3496, 'NAICS', 2037, 81, 1, 2072, 8121, 3),
(3497, 'NAICS', 1726, 561, 2, 1769, 561612, 5),
(3498, 'SEC', 2605, 5200, 2, 2608, 5270, 3),
(3499, 'NAICS', 1076, 4249, 3, 1081, 424930, 5),
(3500, 'NAICS', 1798, 5622, 3, 1803, 562219, 5),
(3501, 'SIC', 3077, 2290, 3, 3078, 2295, 4),
(3502, 'NAICS', 1726, 561, 2, 1778, 56172, 4),
(3503, 'SIC', 3050, 2200, 2, 3059, 2250, 3),
(3504, 'NAICS', 98, 113, 2, 100, 113110, 5),
(3505, 'SEC', 2458, 3700, 2, 2470, 3740, 3),
(3506, 'SIC', 3595, 3990, 3, 3597, 3993, 4),
(3507, 'NAICS', 1015, 424, 2, 1079, 424920, 5),
(3508, 'SIC', 3380, 3430, 3, 3383, 3433, 4),
(3509, 'NAICS', 1672, 5416, 3, 1678, 541618, 5),
(3510, 'NAICS', 1813, 611, 2, 1818, 611210, 5),
(3511, 'SEC', 2791, 20, 1, 2386, 3411, 4),
(3512, 'SEC', 2591, 5100, 2, 2596, 5140, 3),
(3513, 'NAICS', 1624, 54, 1, 1680, 54162, 4),
(3514, 'SEC', 2791, 20, 1, 2469, 3730, 3),
(3515, 'NAICS', 205, 23, 1, 276, 238990, 5),
(3516, 'SEC', 2774, 8700, 2, 2776, 8711, 4),
(3517, 'SIC', 2982, 2000, 2, 3007, 2048, 4),
(3518, 'NAICS', 1625, 541, 2, 1689, 5418, 3),
(3519, 'SEC', 2342, 3000, 2, 2345, 3020, 3),
(3520, 'NAICS', 1718, 55, 1, 1722, 551111, 5),
(3521, 'SIC', 2825, 200, 2, 2842, 272, 4),
(3522, 'NAICS', 132, 21, 1, 176, 213112, 5),
(3523, 'NAICS', 1726, 561, 2, 1738, 56132, 4),
(3524, 'SEC', 2791, 20, 1, 2347, 3050, 3),
(3525, 'SIC', 4313, 70, 1, 4227, 8713, 4),
(3526, 'NAICS', 1090, 4251, 3, 1093, 425120, 5),
(3527, 'NAICS', 2003, 72, 1, 2015, 721211, 5),
(3528, 'SIC', 2825, 200, 2, 2828, 212, 4),
(3529, 'SEC', 2791, 20, 1, 2429, 3578, 4),
(3530, 'SEC', 2568, 5000, 2, 2580, 5063, 4),
(3531, 'NAICS', 930, 42, 1, 987, 423730, 5),
(3532, 'NAICS', 1942, 71, 1, 1981, 713110, 5),
(3533, 'SEC', 2795, 60, 1, 2685, 6350, 3),
(3534, 'SIC', 3083, 2300, 2, 3096, 2337, 4),
(3535, 'SIC', 3419, 3500, 2, 3457, 3566, 4),
(3536, 'SIC', 3948, 6200, 2, 3949, 6210, 3),
(3537, 'SEC', 2751, 7990, 3, 2752, 7997, 4),
(3538, 'SIC', 4313, 70, 1, 4032, 7241, 4),
(3539, 'SIC', 4146, 8000, 2, 4148, 8011, 4),
(3540, 'NAICS', 235, 238, 2, 264, 23832, 4),
(3541, 'NAICS', 1076, 4249, 3, 1078, 42491, 4),
(3542, 'SIC', 4308, 20, 1, 3086, 2320, 3),
(3543, 'SIC', 4308, 20, 1, 3335, 3297, 4),
(3544, 'SIC', 4314, 90, 1, 4269, 9410, 3),
(3545, 'SIC', 4308, 20, 1, 3510, 3669, 4),
(3546, 'SIC', 3426, 3530, 3, 3433, 3537, 4),
(3547, 'SIC', 3083, 2300, 2, 3107, 2371, 4),
(3548, 'SIC', 3552, 3800, 2, 3568, 3844, 4),
(3549, 'SIC', 4308, 20, 1, 3371, 3400, 2),
(3550, 'NAICS', 1812, 61, 1, 1813, 611, 2),
(3551, 'NAICS', 1726, 561, 2, 1753, 56145, 4),
(3552, 'SIC', 2884, 1000, 2, 2890, 1031, 4),
(3553, 'NAICS', 1480, 52, 1, 1549, 52421, 4),
(3554, 'SIC', 3526, 3700, 2, 3532, 3716, 4),
(3555, 'NAICS', 81, 11241, 4, 80, 112410, 5),
(3556, 'NAICS', 132, 21, 1, 166, 212325, 5),
(3557, 'NAICS', 138, 212, 2, 157, 21231, 4),
(3558, 'SIC', 3214, 2800, 2, 3233, 2843, 4),
(3559, 'SIC', 4309, 40, 1, 3670, 4725, 4),
(3560, 'NAICS', 997, 42383, 4, 996, 423830, 5),
(3561, 'SIC', 3958, 6300, 2, 3972, 6390, 3),
(3562, 'SIC', 3917, 6000, 2, 3930, 6062, 4),
(3563, 'NAICS', 1403, 511, 2, 1409, 511130, 5),
(3564, 'SIC', 3330, 3290, 3, 3332, 3292, 4),
(3565, 'NAICS', 1536, 524, 2, 1548, 524210, 5),
(3566, 'SEC', 2795, 60, 1, 2669, 6163, 4),
(3567, 'SIC', 3124, 2400, 2, 3146, 2493, 4),
(3568, 'SEC', 2713, 7300, 2, 2728, 7373, 4),
(3569, 'SIC', 3083, 2300, 2, 3087, 2321, 4),
(3570, 'SIC', 3033, 2090, 3, 3038, 2097, 4),
(3571, 'NAICS', 1726, 561, 2, 1730, 5612, 3),
(3572, 'SIC', 3548, 3790, 3, 3551, 3799, 4),
(3573, 'SIC', 4209, 8610, 3, 4210, 8611, 4),
(3574, 'NAICS', 206, 236, 2, 212, 236118, 5),
(3575, 'NAICS', 1, 11, 1, 12, 111150, 5),
(3576, 'SIC', 3655, 4510, 3, 3657, 4513, 4),
(3577, 'NAICS', 1625, 541, 2, 1700, 541860, 5),
(3578, 'SIC', 4313, 70, 1, 4087, 7520, 3),
(3579, 'NAICS', 2204, 928, 2, 2208, 928120, 5),
(3580, 'SEC', 2753, 8000, 2, 2760, 8070, 3),
(3581, 'NAICS', 1420, 5121, 3, 1428, 51219, 4),
(3582, 'SEC', 2791, 20, 1, 2367, 3272, 4),
(3583, 'SIC', 4306, 10, 1, 2907, 1240, 3),
(3584, 'SIC', 3886, 5900, 2, 3908, 5983, 4),
(3585, 'NAICS', 931, 423, 2, 956, 423410, 5),
(3586, 'NAICS', 1625, 541, 2, 1661, 54142, 4),
(3587, 'SIC', 3481, 3610, 3, 3482, 3612, 4),
(3588, 'SIC', 4313, 70, 1, 4110, 7692, 4),
(3589, 'SIC', 3392, 3450, 3, 3394, 3452, 4),
(3590, 'SIC', 4308, 20, 1, 3045, 2121, 4),
(3591, 'NAICS', 2132, 8141, 3, 2134, 81411, 4),
(3592, 'SEC', 2283, 2500, 2, 2286, 2520, 3),
(3593, 'SIC', 4178, 8200, 2, 4186, 8240, 3),
(3594, 'SEC', 2791, 20, 1, 2284, 2510, 3),
(3595, 'NAICS', 1, 11, 1, 65, 1122, 3),
(3596, 'NAICS', 2124, 81392, 4, 2123, 813920, 5),
(3597, 'NAICS', 2176, 924, 2, 2177, 9241, 3),
(3598, 'SEC', 2526, 4500, 2, 2532, 4580, 3),
(3599, 'SIC', 4311, 52, 1, 3839, 5511, 4),
(3600, 'SIC', 4308, 20, 1, 3564, 3840, 3),
(3601, 'SIC', 4223, 8700, 2, 4237, 8742, 4),
(3602, 'SIC', 4017, 7200, 2, 4030, 7231, 4),
(3603, 'NAICS', 1904, 623, 2, 1907, 62311, 4),
(3604, 'NAICS', 2135, 92, 1, 2184, 925110, 5),
(3605, 'SIC', 4146, 8000, 2, 4159, 8051, 4),
(3606, 'SIC', 4312, 60, 1, 3937, 6100, 2),
(3607, 'NAICS', 2135, 92, 1, 2203, 92711, 4),
(3608, 'NAICS', 931, 423, 2, 1001, 42385, 4),
(3609, 'NAICS', 117, 115, 2, 126, 1152, 3),
(3610, 'NAICS', 1625, 541, 2, 1686, 541712, 5),
(3611, 'NAICS', 1734, 56131, 4, 1735, 561311, 5),
(3612, 'SIC', 3083, 2300, 2, 3123, 2399, 4),
(3613, 'SEC', 2302, 2700, 2, 2304, 2711, 4),
(3614, 'NAICS', 1904, 623, 2, 1908, 6232, 3),
(3615, 'SIC', 4308, 20, 1, 3300, 3199, 4),
(3616, 'SIC', 3419, 3500, 2, 3426, 3530, 3),
(3617, 'SIC', 3264, 3020, 3, 3265, 3021, 4),
(3618, 'NAICS', 1, 11, 1, 31, 111333, 5),
(3619, 'SIC', 4308, 20, 1, 3229, 2836, 4),
(3620, 'SIC', 4313, 70, 1, 4224, 8710, 3),
(3621, 'NAICS', 68, 1123, 3, 76, 11234, 4),
(3622, 'NAICS', 47, 11192, 4, 46, 111920, 5),
(3623, 'NAICS', 1640, 5413, 3, 1647, 541340, 5),
(3624, 'NAICS', 2166, 923, 2, 2171, 92312, 4),
(3625, 'NAICS', 1584, 53131, 4, 1585, 531311, 5),
(3626, 'NAICS', 1725, 56, 1, 1755, 561491, 5),
(3627, 'NAICS', 1920, 624, 2, 1932, 624221, 5),
(3628, 'SEC', 2293, 2610, 3, 2294, 2611, 4),
(3629, 'SEC', 2500, 3900, 2, 2501, 3910, 3),
(3630, 'NAICS', 1625, 541, 2, 1650, 54135, 4),
(3631, 'NAICS', 1625, 541, 2, 1655, 541380, 5),
(3632, 'SEC', 2247, 2030, 3, 2248, 2033, 4),
(3633, 'SIC', 3715, 5000, 2, 3754, 5087, 4),
(3634, 'NAICS', 218, 237, 2, 219, 2371, 3),
(3635, 'SEC', 2796, 70, 1, 2713, 7300, 2),
(3636, 'SIC', 4309, 40, 1, 3609, 4120, 3),
(3637, 'SIC', 3526, 3700, 2, 3551, 3799, 4),
(3638, 'SIC', 3371, 3400, 2, 3385, 3441, 4),
(3639, 'NAICS', 2037, 81, 1, 2054, 811211, 5),
(3640, 'SIC', 3716, 5010, 3, 3719, 5014, 4),
(3641, 'SIC', 3576, 3900, 2, 3597, 3993, 4),
(3642, 'NAICS', 1402, 51, 1, 1405, 511110, 5),
(3643, 'SIC', 4306, 10, 1, 2916, 1382, 4),
(3644, 'SIC', 4308, 20, 1, 3560, 3825, 4),
(3645, 'NAICS', 979, 42362, 4, 978, 423620, 5),
(3646, 'NAICS', 1921, 6241, 3, 1925, 62412, 4),
(3647, 'NAICS', 2037, 81, 1, 2096, 81292, 4),
(3648, 'NAICS', 1570, 531, 2, 1584, 53131, 4),
(3649, 'NAICS', 946, 4233, 3, 949, 423320, 5),
(3650, 'SEC', 2791, 20, 1, 2298, 2631, 4),
(3651, 'SIC', 3262, 3010, 3, 3263, 3011, 4),
(3652, 'SEC', 2342, 3000, 2, 2350, 3081, 4),
(3653, 'NAICS', 1598, 5322, 3, 1604, 53223, 4),
(3654, 'SIC', 3680, 4800, 2, 3690, 4841, 4),
(3655, 'NAICS', 1035, 4244, 3, 1051, 42448, 4),
(3656, 'NAICS', 1823, 6114, 3, 1825, 61141, 4),
(3657, 'SIC', 4314, 90, 1, 4286, 9611, 4),
(3658, 'SIC', 4308, 20, 1, 3191, 2710, 3),
(3659, 'SIC', 4146, 8000, 2, 4147, 8010, 3),
(3660, 'NAICS', 955, 4234, 3, 968, 423490, 5),
(3661, 'NAICS', 1904, 623, 2, 1909, 623210, 5),
(3662, 'NAICS', 1970, 7121, 3, 1971, 712110, 5),
(3663, 'NAICS', 1, 11, 1, 68, 1123, 3),
(3664, 'NAICS', 1726, 561, 2, 1767, 56161, 4),
(3665, 'NAICS', 1495, 5222, 3, 1500, 52229, 4),
(3666, 'NAICS', 2071, 812, 2, 2087, 81231, 4),
(3667, 'SIC', 4306, 10, 1, 2930, 1459, 4),
(3668, 'SIC', 4306, 10, 1, 2895, 1061, 4),
(3669, 'NAICS', 1715, 54194, 4, 1714, 541940, 5),
(3670, 'SEC', 2403, 3500, 2, 2429, 3578, 4),
(3671, 'SIC', 3544, 3760, 3, 3545, 3761, 4),
(3672, 'SIC', 4305, 1, 1, 2862, 761, 4),
(3673, 'NAICS', 133, 211, 2, 135, 21111, 4),
(3674, 'SIC', 4314, 90, 1, 4266, 9310, 3),
(3675, 'SEC', 2796, 70, 1, 2712, 7200, 2),
(3676, 'SIC', 4223, 8700, 2, 4239, 8744, 4),
(3677, 'NAICS', 1404, 5111, 3, 1408, 51112, 4),
(3678, 'NAICS', 930, 42, 1, 1017, 424110, 5),
(3679, 'SEC', 2704, 6790, 3, 2706, 6794, 4),
(3680, 'SIC', 4308, 20, 1, 3054, 2221, 4),
(3681, 'SIC', 3395, 3460, 3, 3396, 3462, 4),
(3682, 'NAICS', 1689, 5418, 3, 1700, 541860, 5),
(3683, 'SIC', 4308, 20, 1, 3128, 2421, 4),
(3684, 'SIC', 4307, 15, 1, 2951, 1620, 3),
(3685, 'SIC', 2826, 210, 3, 2827, 211, 4),
(3686, 'NAICS', 991, 4238, 3, 1000, 423850, 5),
(3687, 'NAICS', 43, 1119, 3, 48, 111930, 5),
(3688, 'SIC', 2847, 700, 2, 2849, 711, 4),
(3689, 'SIC', 3576, 3900, 2, 3578, 3911, 4),
(3690, 'SIC', 3451, 3560, 3, 3454, 3563, 4),
(3691, 'NAICS', 1569, 53, 1, 1610, 532310, 5),
(3692, 'NAICS', 1813, 611, 2, 1845, 611692, 5),
(3693, 'NAICS', 936, 42312, 4, 935, 423120, 5),
(3694, 'NAICS', 1570, 531, 2, 1573, 53111, 4),
(3695, 'NAICS', 1706, 5419, 3, 1713, 54193, 4),
(3696, 'SIC', 3190, 2700, 2, 3191, 2710, 3),
(3697, 'SIC', 3583, 3940, 3, 3586, 3949, 4),
(3698, 'SIC', 3167, 2600, 2, 3179, 2657, 4),
(3699, 'NAICS', 972, 42351, 4, 971, 423510, 5),
(3700, 'SIC', 4308, 20, 1, 3115, 2390, 3),
(3701, 'SIC', 3837, 5500, 2, 3841, 5521, 4),
(3702, 'NAICS', 2037, 81, 1, 2056, 811213, 5),
(3703, 'NAICS', 930, 42, 1, 1073, 42481, 4),
(3704, 'SIC', 3636, 4400, 2, 3641, 4430, 3),
(3705, 'SIC', 2813, 170, 3, 2815, 172, 4),
(3706, 'NAICS', 2, 111, 2, 46, 111920, 5),
(3707, 'NAICS', 219, 2371, 3, 222, 237120, 5),
(3708, 'NAICS', 1061, 4246, 3, 1065, 42469, 4),
(3709, 'NAICS', 1598, 5322, 3, 1608, 532299, 5),
(3710, 'NAICS', 931, 423, 2, 980, 423690, 5),
(3711, 'SEC', 2623, 5600, 2, 2625, 5621, 4),
(3712, 'SIC', 4308, 20, 1, 3445, 3552, 4),
(3713, 'NAICS', 1726, 561, 2, 1750, 561440, 5),
(3714, 'SIC', 3620, 4200, 2, 3626, 4220, 3),
(3715, 'SIC', 3861, 5640, 3, 3862, 5641, 4),
(3716, 'NAICS', 1591, 532, 2, 1617, 53242, 4),
(3717, 'SEC', 4317, 4990, 2, 4318, 4991, 3),
(3718, 'SEC', 2540, 4810, 3, 2541, 4812, 4),
(3719, 'NAICS', 1895, 6221, 3, 1897, 62211, 4),
(3720, 'NAICS', 180, 22, 1, 189, 221116, 5),
(3721, 'NAICS', 1850, 62, 1, 1912, 62322, 4),
(3722, 'SIC', 3576, 3900, 2, 3585, 3944, 4),
(3723, 'SIC', 4065, 7370, 3, 4069, 7374, 4),
(3724, 'NAICS', 930, 42, 1, 1029, 424320, 5),
(3725, 'NAICS', 1725, 56, 1, 1808, 56292, 4),
(3726, 'SIC', 2982, 2000, 2, 2986, 2015, 4),
(3727, 'NAICS', 1725, 56, 1, 1764, 561591, 5),
(3728, 'NAICS', 2037, 81, 1, 2038, 811, 2),
(3729, 'NAICS', 2135, 92, 1, 2186, 925120, 5),
(3730, 'SIC', 3225, 2830, 3, 3227, 2834, 4),
(3731, 'NAICS', 1718, 55, 1, 1724, 551114, 5),
(3732, 'NAICS', 110, 11411, 4, 113, 114119, 5),
(3733, 'NAICS', 930, 42, 1, 1076, 4249, 3),
(3734, 'SIC', 4153, 8040, 3, 4157, 8049, 4),
(3735, 'SIC', 2805, 130, 3, 2806, 131, 4),
(3736, 'SEC', 2791, 20, 1, 2330, 2844, 4),
(3737, 'NAICS', 1640, 5413, 3, 1656, 54138, 4),
(3738, 'NAICS', 1894, 622, 2, 1902, 622310, 5),
(3739, 'SIC', 4308, 20, 1, 3381, 3431, 4),
(3740, 'NAICS', 1672, 5416, 3, 1681, 541690, 5),
(3741, 'SIC', 3083, 2300, 2, 3106, 2370, 3),
(3742, 'SIC', 3552, 3800, 2, 3571, 3851, 4),
(3743, 'SIC', 3667, 4700, 2, 3679, 4789, 4),
(3744, 'SIC', 3869, 5700, 2, 3878, 5731, 4),
(3745, 'SIC', 4305, 1, 1, 2799, 110, 3),
(3746, 'NAICS', 930, 42, 1, 931, 423, 2),
(3747, 'NAICS', 1015, 424, 2, 1063, 42461, 4),
(3748, 'SIC', 4308, 20, 1, 3482, 3612, 4),
(3749, 'SEC', 2438, 3620, 3, 2439, 3621, 4),
(3750, 'NAICS', 1403, 511, 2, 1406, 51111, 4),
(3751, 'NAICS', 1580, 5312, 3, 1582, 53121, 4),
(3752, 'SIC', 3511, 3670, 3, 3519, 3679, 4),
(3753, 'SIC', 4081, 7500, 2, 4086, 7519, 4),
(3754, 'NAICS', 2189, 9261, 3, 2199, 92615, 4),
(3755, 'SEC', 2791, 20, 1, 2314, 2761, 4),
(3756, 'NAICS', 1480, 52, 1, 1543, 524127, 5),
(3757, 'SIC', 3083, 2300, 2, 3094, 2331, 4),
(3758, 'SIC', 4308, 20, 1, 3142, 2451, 4),
(3759, 'SIC', 4040, 7300, 2, 4058, 7350, 3),
(3760, 'NAICS', 213, 2362, 3, 216, 236220, 5),
(3761, 'SIC', 4308, 20, 1, 3071, 2270, 3),
(3762, 'NAICS', 235, 238, 2, 254, 238210, 5),
(3763, 'SEC', 2218, 1200, 2, 2219, 1220, 3),
(3764, 'SEC', 2403, 3500, 2, 2432, 3585, 4),
(3765, 'SIC', 4306, 10, 1, 2934, 1479, 4),
(3766, 'NAICS', 1733, 5613, 3, 1738, 56132, 4),
(3767, 'NAICS', 1035, 4244, 3, 1049, 42447, 4),
(3768, 'SEC', 2792, 40, 1, 2522, 4231, 4),
(3769, 'SIC', 3050, 2200, 2, 3076, 2284, 4),
(3770, 'NAICS', 1657, 5414, 3, 1660, 541420, 5),
(3771, 'NAICS', 236, 2381, 3, 239, 238120, 5),
(3772, 'SIC', 4313, 70, 1, 4118, 7822, 4),
(3773, 'SIC', 3574, 3870, 3, 3575, 3873, 4),
(3774, 'SIC', 4195, 8330, 3, 4196, 8331, 4),
(3775, 'SIC', 3083, 2300, 2, 3084, 2310, 3),
(3776, 'NAICS', 197, 22121, 4, 196, 221210, 5),
(3777, 'SIC', 3918, 6010, 3, 3920, 6019, 4),
(3778, 'SIC', 4146, 8000, 2, 4156, 8043, 4),
(3779, 'NAICS', 1683, 5417, 3, 1685, 541711, 5),
(3780, 'NAICS', 205, 23, 1, 215, 23621, 4),
(3781, 'SIC', 4308, 20, 1, 3204, 2760, 3),
(3782, 'SIC', 3371, 3400, 2, 3377, 3423, 4),
(3783, 'SIC', 3480, 3600, 2, 3485, 3621, 4),
(3784, 'NAICS', 102, 1132, 3, 103, 113210, 5),
(3785, 'SIC', 4307, 15, 1, 2943, 1530, 3),
(3786, 'SIC', 4309, 40, 1, 3618, 4170, 3),
(3787, 'SIC', 4309, 40, 1, 3712, 4961, 4),
(3788, 'NAICS', 1584, 53131, 4, 1586, 531312, 5),
(3789, 'NAICS', 2093, 8129, 3, 2095, 81291, 4),
(3790, 'SIC', 4146, 8000, 2, 4162, 8060, 3),
(3791, 'SIC', 4313, 70, 1, 4185, 8231, 4),
(3792, 'NAICS', 235, 238, 2, 252, 23819, 4),
(3793, 'SEC', 2675, 6280, 3, 2676, 6282, 4),
(3794, 'NAICS', 76, 11234, 4, 75, 112340, 5),
(3795, 'SIC', 3595, 3990, 3, 3596, 3991, 4),
(3796, 'NAICS', 205, 23, 1, 241, 238130, 5),
(3797, 'SIC', 4308, 20, 1, 3319, 3263, 4),
(3798, 'SIC', 2955, 1700, 2, 2961, 1731, 4),
(3799, 'SIC', 4308, 20, 1, 3367, 3369, 4),
(3800, 'SIC', 2939, 1500, 2, 2942, 1522, 4),
(3801, 'SIC', 4309, 40, 1, 3680, 4800, 2),
(3802, 'NAICS', 1813, 611, 2, 1819, 61121, 4),
(3803, 'SEC', 2302, 2700, 2, 2308, 2731, 4),
(3804, 'NAICS', 1094, 42512, 4, 1093, 425120, 5),
(3805, 'SEC', 2792, 40, 1, 2521, 4230, 3),
(3806, 'SIC', 3419, 3500, 2, 3470, 3582, 4),
(3807, 'NAICS', 1402, 51, 1, 1427, 512132, 5),
(3808, 'NAICS', 2103, 813, 2, 2130, 81399, 4),
(3809, 'SEC', 2792, 40, 1, 2542, 4813, 4),
(3810, 'SIC', 3903, 5960, 3, 3905, 5962, 4),
(3811, 'NAICS', 1804, 5629, 3, 1811, 562998, 5),
(3812, 'NAICS', 2103, 813, 2, 2114, 813311, 5),
(3813, 'NAICS', 1813, 611, 2, 1841, 611630, 5),
(3814, 'NAICS', 128, 11521, 4, 127, 115210, 5),
(3815, 'NAICS', 1480, 52, 1, 1487, 522110, 5),
(3816, 'SIC', 4308, 20, 1, 3358, 3354, 4),
(3817, 'NAICS', 1015, 424, 2, 1083, 424940, 5),
(3818, 'NAICS', 1403, 511, 2, 1413, 51119, 4),
(3819, 'NAICS', 181, 221, 2, 188, 221115, 5),
(3820, 'SIC', 3756, 5090, 3, 3758, 5092, 4),
(3821, 'SIC', 4312, 60, 1, 3948, 6200, 2),
(3822, 'SIC', 3190, 2700, 2, 3204, 2760, 3),
(3823, 'SIC', 3577, 3910, 3, 3579, 3914, 4),
(3824, 'SIC', 4308, 20, 1, 3483, 3613, 4),
(3825, 'NAICS', 119, 11511, 4, 123, 115114, 5),
(3826, 'SIC', 4007, 7000, 2, 4013, 7032, 4),
(3827, 'SEC', 2794, 52, 1, 2648, 5990, 3),
(3828, 'SIC', 4312, 60, 1, 3942, 6150, 3),
(3829, 'SEC', 2791, 20, 1, 2356, 3210, 3),
(3830, 'SIC', 4312, 60, 1, 3926, 6035, 4),
(3831, 'SEC', 2795, 60, 1, 2665, 6153, 4),
(3832, 'SIC', 4308, 20, 1, 3404, 3480, 3),
(3833, 'NAICS', 1747, 56143, 4, 1748, 561431, 5),
(3834, 'NAICS', 1985, 7132, 3, 1989, 71329, 4),
(3835, 'NAICS', 2003, 72, 1, 2009, 72112, 4),
(3836, 'SEC', 2424, 3570, 3, 4315, 3576, 4),
(3837, 'SIC', 4311, 52, 1, 3881, 5736, 4),
(3838, 'SIC', 4313, 70, 1, 4079, 7384, 4),
(3839, 'SIC', 3287, 3140, 3, 3290, 3144, 4),
(3840, 'SIC', 4314, 90, 1, 4274, 9441, 4),
(3841, 'SIC', 4313, 70, 1, 4125, 7900, 2),
(3842, 'NAICS', 1799, 56221, 4, 1803, 562219, 5),
(3843, 'NAICS', 79, 1124, 3, 81, 11241, 4),
(3844, 'SIC', 4146, 8000, 2, 4161, 8059, 4),
(3845, 'SIC', 4311, 52, 1, 3891, 5930, 3),
(3846, 'SIC', 3214, 2800, 2, 3217, 2813, 4),
(3847, 'SIC', 3972, 6390, 3, 3973, 6399, 4),
(3848, 'SIC', 4247, 9100, 2, 4253, 9131, 4),
(3849, 'NAICS', 1569, 53, 1, 1581, 531210, 5),
(3850, 'SIC', 3401, 3470, 3, 3403, 3479, 4),
(3851, 'SIC', 4305, 1, 1, 2840, 270, 3),
(3852, 'SIC', 4309, 40, 1, 3634, 4310, 3),
(3853, 'NAICS', 1554, 525, 2, 1555, 5251, 3),
(3854, 'NAICS', 2037, 81, 1, 2045, 81112, 4),
(3855, 'SIC', 4062, 7360, 3, 4063, 7361, 4),
(3856, 'NAICS', 156, 2123, 3, 157, 21231, 4),
(3857, 'NAICS', 1725, 56, 1, 1805, 562910, 5),
(3858, 'SEC', 2221, 1300, 2, 2222, 1310, 3),
(3859, 'SIC', 3026, 2080, 3, 3028, 2083, 4),
(3860, 'SEC', 2574, 5040, 3, 2575, 5045, 4),
(3861, 'NAICS', 1625, 541, 2, 1654, 54137, 4),
(3862, 'SEC', 2552, 4900, 2, 2565, 4953, 4),
(3863, 'SIC', 3869, 5700, 2, 3879, 5734, 4),
(3864, 'NAICS', 1794, 56211, 4, 1797, 562119, 5),
(3865, 'SIC', 3419, 3500, 2, 3465, 3577, 4),
(3866, 'NAICS', 219, 2371, 3, 220, 237110, 5),
(3867, 'NAICS', 1402, 51, 1, 1462, 5179, 3),
(3868, 'SIC', 3680, 4800, 2, 3682, 4812, 4),
(3869, 'SEC', 2488, 3840, 3, 2492, 3844, 4),
(3870, 'NAICS', 1063, 42461, 4, 1062, 424610, 5),
(3871, 'SIC', 4308, 20, 1, 3239, 2865, 4),
(3872, 'SIC', 4313, 70, 1, 4139, 7990, 3),
(3873, 'NAICS', 931, 423, 2, 965, 42345, 4),
(3874, 'SIC', 3938, 6110, 3, 3939, 6111, 4),
(3875, 'NAICS', 930, 42, 1, 1000, 423850, 5),
(3876, 'NAICS', 1569, 53, 1, 1577, 53113, 4),
(3877, 'SIC', 4309, 40, 1, 3711, 4960, 3),
(3878, 'SIC', 4308, 20, 1, 3519, 3679, 4),
(3879, 'NAICS', 1591, 532, 2, 1594, 532111, 5),
(3880, 'SIC', 3375, 3420, 3, 3378, 3425, 4),
(3881, 'SIC', 4305, 1, 1, 2869, 810, 3),
(3882, 'SIC', 3756, 5090, 3, 3760, 5094, 4),
(3883, 'NAICS', 1, 11, 1, 47, 11192, 4),
(3884, 'SEC', 2794, 52, 1, 2633, 5730, 3),
(3885, 'NAICS', 1035, 4244, 3, 1046, 424460, 5),
(3886, 'SIC', 4313, 70, 1, 4228, 8720, 3),
(3887, 'SIC', 3125, 2410, 3, 3126, 2411, 4),
(3888, 'NAICS', 1471, 5191, 3, 1472, 519110, 5),
(3889, 'NAICS', 1035, 4244, 3, 1045, 42445, 4),
(3890, 'SEC', 2791, 20, 1, 2432, 3585, 4),
(3891, 'SIC', 4309, 40, 1, 3665, 4613, 4),
(3892, 'NAICS', 2025, 72232, 4, 2024, 722320, 5),
(3893, 'SEC', 2539, 4800, 2, 2547, 4833, 4),
(3894, 'SEC', 2355, 3200, 2, 2368, 3280, 3),
(3895, 'SIC', 4312, 60, 1, 3979, 6512, 4),
(3896, 'SIC', 4313, 70, 1, 4098, 7542, 4),
(3897, 'NAICS', 1015, 424, 2, 1082, 42493, 4),
(3898, 'SIC', 3715, 5000, 2, 3726, 5032, 4),
(3899, 'SIC', 3180, 2670, 3, 3186, 2676, 4),
(3900, 'SIC', 4313, 70, 1, 4244, 8900, 2),
(3901, 'SIC', 4313, 70, 1, 4037, 7290, 3),
(3902, 'SIC', 2928, 1450, 3, 2929, 1455, 4),
(3903, 'SIC', 4314, 90, 1, 4296, 9661, 4),
(3904, 'SIC', 4313, 70, 1, 4171, 8090, 3),
(3905, 'SIC', 4040, 7300, 2, 4070, 7375, 4),
(3906, 'SEC', 2443, 3650, 3, 2444, 3651, 4),
(3907, 'NAICS', 1624, 54, 1, 1633, 541199, 5),
(3908, 'SIC', 4308, 20, 1, 3140, 2449, 4),
(3909, 'NAICS', 98, 113, 2, 101, 11311, 4),
(3910, 'SIC', 2966, 1750, 3, 2968, 1752, 4),
(3911, 'SIC', 3605, 4100, 2, 3615, 4142, 4),
(3912, 'NAICS', 1774, 5617, 3, 1775, 561710, 5),
(3913, 'SEC', 2709, 7000, 2, 2711, 7011, 4),
(3914, 'SIC', 3576, 3900, 2, 3596, 3991, 4),
(3915, 'SIC', 3762, 5100, 2, 3771, 5136, 4),
(3916, 'SEC', 2703, 6700, 2, 2706, 6794, 4),
(3917, 'SIC', 3552, 3800, 2, 3574, 3870, 3),
(3918, 'SIC', 3626, 4220, 3, 3627, 4221, 4),
(3919, 'SIC', 2982, 2000, 2, 2995, 2033, 4),
(3920, 'SIC', 2918, 1400, 2, 2933, 1475, 4),
(3921, 'SIC', 4308, 20, 1, 3081, 2298, 4),
(3922, 'SEC', 2568, 5000, 2, 2571, 5020, 3),
(3923, 'SIC', 3480, 3600, 2, 3515, 3675, 4),
(3924, 'NAICS', 1923, 62411, 4, 1922, 624110, 5),
(3925, 'NAICS', 1004, 4239, 3, 1005, 423910, 5),
(3926, 'SIC', 3576, 3900, 2, 3577, 3910, 3),
(3927, 'SIC', 4308, 20, 1, 3370, 3399, 4),
(3928, 'NAICS', 1904, 623, 2, 1918, 623990, 5),
(3929, 'NAICS', 1, 11, 1, 98, 113, 2),
(3930, 'NAICS', 162, 21232, 4, 165, 212324, 5),
(3931, 'SIC', 4065, 7370, 3, 4073, 7378, 4),
(3932, 'SIC', 3729, 5040, 3, 3731, 5044, 4),
(3933, 'SIC', 4309, 40, 1, 3613, 4140, 3),
(3934, 'SEC', 2355, 3200, 2, 2357, 3211, 4),
(3935, 'SIC', 3970, 6370, 3, 3971, 6371, 4),
(3936, 'SIC', 4313, 70, 1, 4200, 8361, 4),
(3937, 'SIC', 3931, 6080, 3, 3932, 6081, 4),
(3938, 'NAICS', 1725, 56, 1, 1745, 561421, 5),
(3939, 'NAICS', 1054, 4245, 3, 1060, 42459, 4),
(3940, 'NAICS', 1076, 4249, 3, 1087, 424990, 5),
(3941, 'SIC', 4308, 20, 1, 3565, 3841, 4),
(3942, 'NAICS', 1851, 621, 2, 1878, 621492, 5),
(3943, 'NAICS', 1654, 54137, 4, 1653, 541370, 5),
(3944, 'SIC', 4306, 10, 1, 2885, 1010, 3),
(3945, 'SIC', 3526, 3700, 2, 3539, 3732, 4),
(3946, 'NAICS', 957, 42341, 4, 956, 423410, 5),
(3947, 'SIC', 4308, 20, 1, 3028, 2083, 4),
(3948, 'SIC', 2918, 1400, 2, 2923, 1423, 4),
(3949, 'NAICS', 1562, 5259, 3, 1566, 52592, 4),
(3950, 'SEC', 2650, 6020, 3, 2652, 6022, 4),
(3951, 'NAICS', 1, 11, 1, 106, 113310, 5),
(3952, 'SIC', 4308, 20, 1, 3323, 3271, 4),
(3953, 'NAICS', 1041, 42443, 4, 1040, 424430, 5),
(3954, 'NAICS', 1480, 52, 1, 1554, 525, 2),
(3955, 'NAICS', 1850, 62, 1, 1902, 622310, 5),
(3956, 'SIC', 4308, 20, 1, 3535, 3724, 4),
(3957, 'SEC', 2791, 20, 1, 2348, 3060, 3),
(3958, 'SEC', 2791, 20, 1, 2496, 3860, 3),
(3959, 'SEC', 2766, 8100, 2, 2767, 8110, 3),
(3960, 'NAICS', 1970, 7121, 3, 1973, 712120, 5),
(3961, 'SIC', 4313, 70, 1, 4102, 7622, 4),
(3962, 'NAICS', 1404, 5111, 3, 1407, 511120, 5),
(3963, 'NAICS', 1624, 54, 1, 1629, 541120, 5),
(3964, 'NAICS', 275, 23891, 4, 274, 238910, 5),
(3965, 'NAICS', 2135, 92, 1, 2201, 9271, 3),
(3966, 'SIC', 3527, 3710, 3, 3532, 3716, 4),
(3967, 'SIC', 3371, 3400, 2, 3417, 3498, 4),
(3968, 'NAICS', 1514, 5231, 3, 1521, 523140, 5),
(3969, 'NAICS', 2093, 8129, 3, 2097, 812921, 5),
(3970, 'SEC', 2302, 2700, 2, 2306, 2721, 4),
(3971, 'NAICS', 1480, 52, 1, 1518, 52312, 4),
(3972, 'SIC', 4308, 20, 1, 3322, 3270, 3),
(3973, 'SEC', 2791, 20, 1, 2283, 2500, 2),
(3974, 'SEC', 2793, 50, 1, 2597, 5141, 4),
(3975, 'SIC', 3870, 5710, 3, 3871, 5712, 4),
(3976, 'NAICS', 2135, 92, 1, 2193, 92612, 4),
(3977, 'NAICS', 1, 11, 1, 15, 11116, 4),
(3978, 'SEC', 2791, 20, 1, 2275, 2390, 3),
(3979, 'SEC', 2796, 70, 1, 2765, 8093, 4),
(3980, 'SIC', 4007, 7000, 2, 4008, 7010, 3),
(3981, 'SIC', 3371, 3400, 2, 3402, 3471, 4),
(3982, 'NAICS', 235, 238, 2, 257, 23822, 4),
(3983, 'SIC', 4307, 15, 1, 2939, 1500, 2),
(3984, 'SIC', 4313, 70, 1, 4094, 7537, 4),
(3985, 'NAICS', 1018, 42411, 4, 1017, 424110, 5),
(3986, 'SIC', 4308, 20, 1, 3264, 3020, 3),
(3987, 'NAICS', 270, 23835, 4, 269, 238350, 5),
(3988, 'NAICS', 1910, 62321, 4, 1909, 623210, 5),
(3989, 'SIC', 4309, 40, 1, 3706, 4941, 4),
(3990, 'SIC', 4305, 1, 1, 2866, 782, 4),
(3991, 'SIC', 4310, 50, 1, 3722, 5021, 4),
(3992, 'NAICS', 1990, 7139, 3, 1996, 71393, 4),
(3993, 'NAICS', 1015, 424, 2, 1059, 424590, 5),
(3994, 'SEC', 2553, 4910, 3, 2554, 4911, 4),
(3995, 'SIC', 4308, 20, 1, 3345, 3321, 4),
(3996, 'NAICS', 1969, 712, 2, 1977, 712190, 5),
(3997, 'SIC', 3480, 3600, 2, 3506, 3652, 4),
(3998, 'SIC', 3552, 3800, 2, 3562, 3827, 4),
(3999, 'NAICS', 931, 423, 2, 1004, 4239, 3),
(4000, 'NAICS', 40, 11142, 4, 41, 111421, 5),
(4001, 'NAICS', 205, 23, 1, 262, 23831, 4),
(4002, 'SIC', 3214, 2800, 2, 3249, 2893, 4),
(4003, 'SIC', 3576, 3900, 2, 3582, 3931, 4),
(4004, 'NAICS', 1625, 541, 2, 1639, 541219, 5),
(4005, 'NAICS', 2071, 812, 2, 2095, 81291, 4),
(4006, 'NAICS', 931, 423, 2, 989, 423740, 5),
(4007, 'SIC', 3214, 2800, 2, 3237, 2860, 3),
(4008, 'SIC', 4307, 15, 1, 2958, 1720, 3),
(4009, 'NAICS', 132, 21, 1, 160, 212313, 5),
(4010, 'SEC', 2271, 2300, 2, 2272, 2320, 3),
(4011, 'SIC', 4065, 7370, 3, 4067, 7372, 4),
(4012, 'SIC', 3050, 2200, 2, 3065, 2258, 4),
(4013, 'SEC', 2791, 20, 1, 2436, 3612, 4),
(4014, 'NAICS', 23, 1113, 3, 35, 111339, 5),
(4015, 'SEC', 2789, 10, 1, 2227, 1389, 4),
(4016, 'SIC', 2918, 1400, 2, 2932, 1474, 4),
(4017, 'SIC', 3504, 3650, 3, 3505, 3651, 4),
(4018, 'NAICS', 1617, 53242, 4, 1616, 532420, 5),
(4019, 'NAICS', 2204, 928, 2, 2209, 92812, 4),
(4020, 'NAICS', 2189, 9261, 3, 2197, 92614, 4),
(4021, 'SIC', 4153, 8040, 3, 4154, 8041, 4),
(4022, 'NAICS', 930, 42, 1, 1013, 423990, 5),
(4023, 'SIC', 3148, 2500, 2, 3162, 2541, 4),
(4024, 'NAICS', 2197, 92614, 4, 2196, 926140, 5),
(4025, 'NAICS', 204, 22133, 4, 203, 221330, 5),
(4026, 'SEC', 2794, 52, 1, 2624, 5620, 3),
(4027, 'NAICS', 1402, 51, 1, 1471, 5191, 3),
(4028, 'NAICS', 268, 23834, 4, 267, 238340, 5),
(4029, 'NAICS', 1625, 541, 2, 1656, 54138, 4),
(4030, 'SIC', 4197, 8350, 3, 4198, 8351, 4),
(4031, 'SIC', 4308, 20, 1, 3448, 3555, 4),
(4032, 'SIC', 4313, 70, 1, 4085, 7515, 4),
(4033, 'NAICS', 1071, 4248, 3, 1072, 424810, 5),
(4034, 'NAICS', 2136, 921, 2, 2147, 92115, 4),
(4035, 'SIC', 3419, 3500, 2, 3451, 3560, 3),
(4036, 'NAICS', 2, 111, 2, 45, 11191, 4),
(4037, 'SIC', 3917, 6000, 2, 3926, 6035, 4),
(4038, 'NAICS', 1402, 51, 1, 1455, 51711, 4),
(4039, 'NAICS', 1793, 5621, 3, 1796, 562112, 5),
(4040, 'SIC', 3837, 5500, 2, 3838, 5510, 3),
(4041, 'SIC', 2925, 1440, 3, 2926, 1442, 4),
(4042, 'SIC', 4309, 40, 1, 3696, 4920, 3),
(4043, 'SIC', 4309, 40, 1, 3650, 4491, 4),
(4044, 'NAICS', 1580, 5312, 3, 1581, 531210, 5),
(4045, 'NAICS', 945, 42322, 4, 944, 423220, 5),
(4046, 'NAICS', 1054, 4245, 3, 1055, 424510, 5),
(4047, 'NAICS', 1537, 5241, 3, 1543, 524127, 5),
(4048, 'NAICS', 2171, 92312, 4, 2170, 923120, 5),
(4049, 'NAICS', 1514, 5231, 3, 1516, 52311, 4),
(4050, 'NAICS', 1673, 54161, 4, 1675, 541612, 5),
(4051, 'SEC', 2791, 20, 1, 2312, 2750, 3),
(4052, 'NAICS', 1792, 562, 2, 1802, 562213, 5),
(4053, 'SEC', 2552, 4900, 2, 2554, 4911, 4),
(4054, 'SEC', 2791, 20, 1, 4315, 3576, 4),
(4055, 'SIC', 4308, 20, 1, 3352, 3339, 4),
(4056, 'SIC', 4308, 20, 1, 3177, 2655, 4),
(4057, 'SEC', 2501, 3910, 3, 2502, 3911, 4),
(4058, 'SIC', 3837, 5500, 2, 3842, 5530, 3),
(4059, 'SIC', 4313, 70, 1, 4113, 7800, 2),
(4060, 'NAICS', 235, 238, 2, 242, 23813, 4),
(4061, 'NAICS', 1442, 515, 2, 1447, 515120, 5),
(4062, 'NAICS', 2, 111, 2, 49, 11193, 4),
(4063, 'NAICS', 1566, 52592, 4, 1565, 525920, 5),
(4064, 'SEC', 2796, 70, 1, 2781, 8741, 4),
(4065, 'SIC', 4314, 90, 1, 4250, 9120, 3),
(4066, 'SIC', 3837, 5500, 2, 3846, 5550, 3),
(4067, 'NAICS', 1547, 5242, 3, 1548, 524210, 5),
(4068, 'SIC', 3419, 3500, 2, 3473, 3589, 4),
(4069, 'NAICS', 68, 1123, 3, 71, 112320, 5),
(4070, 'SIC', 4313, 70, 1, 4241, 8800, 2),
(4071, 'NAICS', 1990, 7139, 3, 2000, 71395, 4),
(4072, 'NAICS', 1015, 424, 2, 1075, 42482, 4),
(4073, 'SEC', 2791, 20, 1, 2305, 2720, 3),
(4074, 'SIC', 3355, 3350, 3, 3357, 3353, 4),
(4075, 'SIC', 4313, 70, 1, 4031, 7240, 3),
(4076, 'SIC', 4305, 1, 1, 2871, 830, 3),
(4077, 'NAICS', 1942, 71, 1, 1947, 711120, 5),
(4078, 'NAICS', 1990, 7139, 3, 1999, 713950, 5),
(4079, 'SIC', 3337, 3300, 2, 3356, 3351, 4),
(4080, 'NAICS', 1032, 42433, 4, 1031, 424330, 5),
(4081, 'NAICS', 1402, 51, 1, 1424, 51212, 4),
(4082, 'NAICS', 2135, 92, 1, 2160, 922150, 5),
(4083, 'SEC', 2620, 5500, 2, 2622, 5531, 4),
(4084, 'NAICS', 1569, 53, 1, 1582, 53121, 4),
(4085, 'NAICS', 198, 2213, 3, 202, 22132, 4),
(4086, 'NAICS', 1850, 62, 1, 1900, 62221, 4),
(4087, 'NAICS', 78, 11239, 4, 77, 112390, 5),
(4088, 'NAICS', 1, 11, 1, 63, 112130, 5),
(4089, 'SEC', 2791, 20, 1, 2406, 3523, 4),
(4090, 'SIC', 3108, 2380, 3, 3109, 2381, 4),
(4091, 'SIC', 4308, 20, 1, 3494, 3635, 4),
(4092, 'SIC', 4308, 20, 1, 3512, 3671, 4),
(4093, 'SIC', 4049, 7330, 3, 4052, 7335, 4),
(4094, 'NAICS', 930, 42, 1, 1037, 42441, 4),
(4095, 'NAICS', 1625, 541, 2, 1658, 541410, 5),
(4096, 'SIC', 4308, 20, 1, 3405, 3482, 4),
(4097, 'SEC', 2479, 3820, 3, 2482, 3823, 4),
(4098, 'SIC', 3654, 4500, 2, 3656, 4512, 4),
(4099, 'SIC', 4312, 60, 1, 3961, 6320, 3),
(4100, 'SIC', 4312, 60, 1, 3917, 6000, 2),
(4101, 'NAICS', 1657, 5414, 3, 1663, 54143, 4),
(4102, 'NAICS', 2038, 811, 2, 2047, 811122, 5),
(4103, 'SEC', 2795, 60, 1, 2701, 6550, 3),
(4104, 'SIC', 4313, 70, 1, 4101, 7620, 3),
(4105, 'SIC', 3480, 3600, 2, 3518, 3678, 4),
(4106, 'SIC', 4040, 7300, 2, 4041, 7310, 3),
(4107, 'SEC', 2792, 40, 1, 2552, 4900, 2),
(4108, 'SIC', 4310, 50, 1, 3764, 5111, 4),
(4109, 'SEC', 2396, 3450, 3, 2397, 3451, 4),
(4110, 'SEC', 2792, 40, 1, 2544, 4822, 4),
(4111, 'SEC', 2791, 20, 1, 2457, 3695, 4),
(4112, 'SIC', 3480, 3600, 2, 3497, 3641, 4),
(4113, 'SIC', 4308, 20, 1, 2993, 2030, 3),
(4114, 'NAICS', 84, 1125, 3, 85, 11251, 4),
(4115, 'NAICS', 2038, 811, 2, 2069, 811490, 5),
(4116, 'SIC', 4311, 52, 1, 3819, 5331, 4),
(4117, 'SIC', 4305, 1, 1, 2851, 721, 4),
(4118, 'SIC', 3144, 2490, 3, 3146, 2493, 4),
(4119, 'SIC', 4308, 20, 1, 3169, 2611, 4),
(4120, 'SIC', 4235, 8740, 3, 4240, 8748, 4),
(4121, 'NAICS', 1856, 6212, 3, 1858, 62121, 4),
(4122, 'SIC', 4017, 7200, 2, 4029, 7230, 3),
(4123, 'SEC', 2792, 40, 1, 2553, 4910, 3),
(4124, 'SIC', 4313, 70, 1, 4168, 8072, 4),
(4125, 'NAICS', 1725, 56, 1, 1789, 56192, 4),
(4126, 'SEC', 2793, 50, 1, 2595, 5130, 3),
(4127, 'SEC', 2649, 6000, 2, 2650, 6020, 3),
(4128, 'SIC', 3215, 2810, 3, 3216, 2812, 4),
(4129, 'NAICS', 1726, 561, 2, 1780, 56173, 4),
(4130, 'SEC', 2591, 5100, 2, 2593, 5120, 3),
(4131, 'NAICS', 1791, 56199, 4, 1790, 561990, 5),
(4132, 'NAICS', 955, 4234, 3, 966, 423460, 5),
(4133, 'SIC', 4313, 70, 1, 4206, 8420, 3),
(4134, 'NAICS', 1004, 4239, 3, 1007, 423920, 5),
(4135, 'SIC', 3252, 2900, 2, 3259, 2992, 4),
(4136, 'SIC', 4310, 50, 1, 3740, 5060, 3),
(4137, 'NAICS', 1850, 62, 1, 1931, 62422, 4),
(4138, 'SIC', 3756, 5090, 3, 3761, 5099, 4),
(4139, 'NAICS', 991, 4238, 3, 993, 42381, 4),
(4140, 'NAICS', 1812, 61, 1, 1831, 61151, 4),
(4141, 'NAICS', 2135, 92, 1, 2144, 921140, 5),
(4142, 'NAICS', 135, 21111, 4, 137, 211112, 5),
(4143, 'NAICS', 138, 212, 2, 146, 21221, 4),
(4144, 'SEC', 2434, 3600, 2, 2457, 3695, 4),
(4145, 'SIC', 4307, 15, 1, 2968, 1752, 4),
(4146, 'SIC', 4147, 8010, 3, 4148, 8011, 4),
(4147, 'SIC', 3804, 5200, 2, 3805, 5210, 3),
(4148, 'NAICS', 930, 42, 1, 964, 423450, 5),
(4149, 'SIC', 3337, 3300, 2, 3351, 3334, 4),
(4150, 'SIC', 4308, 20, 1, 3328, 3280, 3),
(4151, 'SIC', 4192, 8300, 2, 4202, 8399, 4),
(4152, 'NAICS', 1, 11, 1, 35, 111339, 5),
(4153, 'NAICS', 1591, 532, 2, 1607, 532292, 5),
(4154, 'NAICS', 2167, 9231, 3, 2169, 92311, 4),
(4155, 'NAICS', 1004, 4239, 3, 1011, 423940, 5),
(4156, 'SIC', 3451, 3560, 3, 3453, 3562, 4),
(4157, 'NAICS', 2072, 8121, 3, 2077, 81219, 4),
(4158, 'SIC', 4309, 40, 1, 3656, 4512, 4),
(4159, 'NAICS', 931, 423, 2, 932, 4231, 3),
(4160, 'SIC', 2820, 180, 3, 2822, 182, 4),
(4161, 'SEC', 2792, 40, 1, 2532, 4580, 3),
(4162, 'NAICS', 1564, 52591, 4, 1563, 525910, 5),
(4163, 'SIC', 2982, 2000, 2, 3033, 2090, 3),
(4164, 'SIC', 3301, 3200, 2, 3333, 3295, 4),
(4165, 'SIC', 3693, 4900, 2, 3710, 4959, 4),
(4166, 'SIC', 4311, 52, 1, 3885, 5813, 4),
(4167, 'SIC', 3762, 5100, 2, 3778, 5144, 4),
(4168, 'SIC', 3115, 2390, 3, 3117, 2392, 4),
(4169, 'SIC', 4308, 20, 1, 3039, 2098, 4),
(4170, 'SIC', 4125, 7900, 2, 4136, 7950, 3),
(4171, 'SIC', 2805, 130, 3, 2810, 139, 4),
(4172, 'NAICS', 1812, 61, 1, 1838, 61161, 4),
(4173, 'NAICS', 2037, 81, 1, 2107, 8132, 3),
(4174, 'SEC', 2713, 7300, 2, 2719, 7340, 3),
(4175, 'SIC', 3050, 2200, 2, 3061, 2252, 4),
(4176, 'NAICS', 144, 2122, 3, 145, 212210, 5),
(4177, 'SIC', 4308, 20, 1, 3166, 2599, 4),
(4178, 'NAICS', 1871, 6214, 3, 1878, 621492, 5),
(4179, 'SIC', 3763, 5110, 3, 3765, 5112, 4),
(4180, 'SIC', 4313, 70, 1, 4152, 8031, 4),
(4181, 'NAICS', 1640, 5413, 3, 1654, 54137, 4),
(4182, 'SIC', 4284, 9600, 2, 4296, 9661, 4),
(4183, 'NAICS', 1402, 51, 1, 1456, 5172, 3),
(4184, 'NAICS', 1885, 6216, 3, 1887, 62161, 4),
(4185, 'NAICS', 1789, 56192, 4, 1788, 561920, 5),
(4186, 'SIC', 2982, 2000, 2, 3029, 2084, 4),
(4187, 'NAICS', 2143, 92113, 4, 2142, 921130, 5),
(4188, 'SEC', 2753, 8000, 2, 2761, 8071, 4),
(4189, 'SIC', 2823, 190, 3, 2824, 191, 4),
(4190, 'SIC', 3108, 2380, 3, 3110, 2384, 4),
(4191, 'NAICS', 1725, 56, 1, 1741, 5614, 3),
(4192, 'NAICS', 1917, 6239, 3, 1918, 623990, 5),
(4193, 'NAICS', 1830, 6115, 3, 1831, 61151, 4),
(4194, 'SEC', 2785, 9700, 2, 2786, 9720, 3),
(4195, 'SIC', 3020, 2070, 3, 3021, 2074, 4),
(4196, 'SEC', 2479, 3820, 3, 2487, 3829, 4),
(4197, 'SIC', 4313, 70, 1, 4051, 7334, 4),
(4198, 'SIC', 3108, 2380, 3, 3112, 2386, 4),
(4199, 'SEC', 2791, 20, 1, 2322, 2821, 4),
(4200, 'SIC', 3744, 5070, 3, 3746, 5074, 4),
(4201, 'NAICS', 2021, 7223, 3, 2023, 72231, 4),
(4202, 'NAICS', 1894, 622, 2, 1900, 62221, 4),
(4203, 'SEC', 2795, 60, 1, 4320, 6170, 3),
(4204, 'NAICS', 1, 11, 1, 121, 115112, 5),
(4205, 'NAICS', 1624, 54, 1, 1651, 541360, 5),
(4206, 'NAICS', 1904, 623, 2, 1917, 6239, 3),
(4207, 'SEC', 2568, 5000, 2, 2587, 5084, 4),
(4208, 'SIC', 3480, 3600, 2, 3498, 3643, 4),
(4209, 'SIC', 3762, 5100, 2, 3800, 5193, 4),
(4210, 'NAICS', 946, 4233, 3, 953, 423390, 5),
(4211, 'SEC', 2774, 8700, 2, 2775, 8710, 3),
(4212, 'SEC', 2434, 3600, 2, 2436, 3612, 4),
(4213, 'SIC', 4308, 20, 1, 3547, 3769, 4),
(4214, 'SIC', 3261, 3000, 2, 3265, 3021, 4),
(4215, 'SIC', 4310, 50, 1, 3780, 5146, 4),
(4216, 'NAICS', 1767, 56161, 4, 1769, 561612, 5),
(4217, 'NAICS', 2004, 721, 2, 2012, 721199, 5),
(4218, 'SEC', 2403, 3500, 2, 4315, 3576, 4),
(4219, 'SIC', 4313, 70, 1, 4108, 7641, 4),
(4220, 'SIC', 4309, 40, 1, 3632, 4231, 4),
(4221, 'NAICS', 2021, 7223, 3, 2022, 722310, 5),
(4222, 'SIC', 3115, 2390, 3, 3120, 2395, 4),
(4223, 'NAICS', 138, 212, 2, 164, 212322, 5),
(4224, 'SIC', 4307, 15, 1, 2978, 1794, 4),
(4225, 'SIC', 4307, 15, 1, 2979, 1795, 4),
(4226, 'SIC', 3225, 2830, 3, 3228, 2835, 4),
(4227, 'SEC', 2403, 3500, 2, 2406, 3523, 4),
(4228, 'SEC', 2371, 3300, 2, 2381, 3357, 4),
(4229, 'NAICS', 2071, 812, 2, 2097, 812921, 5),
(4230, 'NAICS', 235, 238, 2, 236, 2381, 3),
(4231, 'SEC', 2292, 2600, 2, 2294, 2611, 4),
(4232, 'NAICS', 1, 11, 1, 87, 112512, 5),
(4233, 'SIC', 4308, 20, 1, 3066, 2259, 4),
(4234, 'SIC', 4308, 20, 1, 3573, 3861, 4),
(4235, 'SEC', 2413, 3540, 3, 2414, 3541, 4),
(4236, 'NAICS', 1, 11, 1, 51, 11194, 4),
(4237, 'SIC', 3511, 3670, 3, 3512, 3671, 4),
(4238, 'NAICS', 1035, 4244, 3, 1036, 424410, 5),
(4239, 'SIC', 3672, 4730, 3, 3673, 4731, 4),
(4240, 'SIC', 4040, 7300, 2, 4063, 7361, 4),
(4241, 'SEC', 2408, 3530, 3, 2410, 3532, 4),
(4242, 'NAICS', 132, 21, 1, 143, 212113, 5),
(4243, 'SEC', 2767, 8110, 3, 2768, 8111, 4),
(4244, 'SIC', 3552, 3800, 2, 3570, 3850, 3),
(4245, 'SIC', 4311, 52, 1, 3807, 5230, 3),
(4246, 'SIC', 4312, 60, 1, 4001, 6733, 4),
(4247, 'NAICS', 1976, 71213, 4, 1975, 712130, 5),
(4248, 'SEC', 2240, 2000, 2, 2250, 2050, 3),
(4249, 'SIC', 4031, 7240, 3, 4032, 7241, 4),
(4250, 'NAICS', 138, 212, 2, 158, 212311, 5),
(4251, 'NAICS', 217, 23622, 4, 216, 236220, 5),
(4252, 'SIC', 2987, 2020, 3, 2990, 2023, 4),
(4253, 'SIC', 4313, 70, 1, 4178, 8200, 2),
(4254, 'SIC', 3850, 5570, 3, 3851, 5571, 4),
(4255, 'SIC', 4310, 50, 1, 3721, 5020, 3),
(4256, 'SIC', 4311, 52, 1, 3813, 5270, 3),
(4257, 'NAICS', 930, 42, 1, 1086, 42495, 4),
(4258, 'SEC', 2617, 5400, 2, 4319, 5412, 4),
(4259, 'NAICS', 1015, 424, 2, 1041, 42443, 4),
(4260, 'SIC', 3083, 2300, 2, 3122, 2397, 4),
(4261, 'NAICS', 2020, 722, 2, 2032, 72251, 4),
(4262, 'NAICS', 2103, 813, 2, 2127, 813940, 5),
(4263, 'SIC', 3093, 2330, 3, 3094, 2331, 4),
(4264, 'NAICS', 1402, 51, 1, 1446, 515112, 5),
(4265, 'SEC', 2271, 2300, 2, 2273, 2330, 3),
(4266, 'SIC', 4002, 6790, 3, 4003, 6792, 4),
(4267, 'SIC', 3762, 5100, 2, 3765, 5112, 4),
(4268, 'SIC', 2982, 2000, 2, 3034, 2091, 4),
(4269, 'NAICS', 1047, 42446, 4, 1046, 424460, 5),
(4270, 'SIC', 3362, 3360, 3, 3363, 3363, 4),
(4271, 'NAICS', 930, 42, 1, 947, 423310, 5),
(4272, 'NAICS', 139, 2121, 3, 140, 21211, 4),
(4273, 'SIC', 3395, 3460, 3, 3400, 3469, 4),
(4274, 'SIC', 3762, 5100, 2, 3783, 5149, 4),
(4275, 'SIC', 4040, 7300, 2, 4075, 7380, 3),
(4276, 'NAICS', 1481, 521, 2, 1483, 521110, 5),
(4277, 'NAICS', 1726, 561, 2, 1757, 561499, 5),
(4278, 'NAICS', 2037, 81, 1, 2041, 811111, 5),
(4279, 'SIC', 3621, 4210, 3, 3623, 4213, 4),
(4280, 'SIC', 4310, 50, 1, 3719, 5014, 4),
(4281, 'NAICS', 1830, 6115, 3, 1832, 611511, 5),
(4282, 'SIC', 4313, 70, 1, 4078, 7383, 4),
(4283, 'NAICS', 1766, 5616, 3, 1771, 56162, 4),
(4284, 'SIC', 3620, 4200, 2, 3629, 4225, 4),
(4285, 'NAICS', 1624, 54, 1, 1670, 541513, 5),
(4286, 'SEC', 2795, 60, 1, 2659, 6100, 2),
(4287, 'NAICS', 1894, 622, 2, 1895, 6221, 3),
(4288, 'SIC', 3555, 3820, 3, 3559, 3824, 4),
(4289, 'NAICS', 156, 2123, 3, 158, 212311, 5),
(4290, 'SEC', 2731, 7380, 3, 2733, 7384, 4),
(4291, 'SIC', 4308, 20, 1, 3286, 3131, 4),
(4292, 'SEC', 2259, 2100, 2, 2261, 2111, 4),
(4293, 'SEC', 2795, 60, 1, 2678, 6310, 3),
(4294, 'SIC', 4308, 20, 1, 3308, 3231, 4),
(4295, 'NAICS', 19, 1112, 3, 20, 11121, 4),
(4296, 'NAICS', 1404, 5111, 3, 1410, 51113, 4),
(4297, 'SIC', 3371, 3400, 2, 3380, 3430, 3),
(4298, 'SIC', 4311, 52, 1, 3854, 5600, 2),
(4299, 'SIC', 4305, 1, 1, 2822, 182, 4),
(4300, 'NAICS', 930, 42, 1, 1094, 42512, 4),
(4301, 'SIC', 3409, 3490, 3, 3416, 3497, 4),
(4302, 'NAICS', 180, 22, 1, 203, 221330, 5),
(4303, 'NAICS', 2000, 71395, 4, 1999, 713950, 5),
(4304, 'NAICS', 1823, 6114, 3, 1826, 611420, 5),
(4305, 'SIC', 2955, 1700, 2, 2963, 1741, 4),
(4306, 'NAICS', 1625, 541, 2, 1698, 541850, 5),
(4307, 'SIC', 4308, 20, 1, 3044, 2120, 3),
(4308, 'NAICS', 2037, 81, 1, 2077, 81219, 4),
(4309, 'NAICS', 2082, 81221, 4, 2081, 812210, 5),
(4310, 'SEC', 2756, 8050, 3, 2757, 8051, 4),
(4311, 'NAICS', 1944, 7111, 3, 1948, 71112, 4),
(4312, 'SEC', 2762, 8080, 3, 2763, 8082, 4),
(4313, 'SIC', 4308, 20, 1, 3063, 2254, 4),
(4314, 'NAICS', 1944, 7111, 3, 1951, 711190, 5),
(4315, 'SIC', 3911, 5990, 3, 3916, 5999, 4),
(4316, 'SIC', 3945, 6160, 3, 3946, 6162, 4),
(4317, 'SIC', 4312, 60, 1, 3930, 6062, 4),
(4318, 'SEC', 2659, 6100, 2, 2666, 6159, 4),
(4319, 'NAICS', 205, 23, 1, 206, 236, 2),
(4320, 'NAICS', 2139, 92111, 4, 2138, 921110, 5),
(4321, 'SIC', 4017, 7200, 2, 4035, 7260, 3),
(4322, 'NAICS', 156, 2123, 3, 164, 212322, 5),
(4323, 'NAICS', 1485, 522, 2, 1499, 52222, 4),
(4324, 'SEC', 2353, 3100, 2, 2354, 3140, 3),
(4325, 'SIC', 3272, 3080, 3, 3276, 3084, 4),
(4326, 'SEC', 2591, 5100, 2, 2603, 5180, 3),
(4327, 'SIC', 3715, 5000, 2, 3749, 5080, 3),
(4328, 'SIC', 4097, 7540, 3, 4099, 7549, 4),
(4329, 'SIC', 4273, 9440, 3, 4274, 9441, 4),
(4330, 'SIC', 4125, 7900, 2, 4138, 7952, 4),
(4331, 'NAICS', 183, 22111, 4, 184, 221111, 5),
(4332, 'NAICS', 1522, 52314, 4, 1521, 523140, 5),
(4333, 'SIC', 4308, 20, 1, 2991, 2024, 4),
(4334, 'SEC', 2796, 70, 1, 2726, 7371, 4),
(4335, 'SIC', 4308, 20, 1, 3051, 2210, 3),
(4336, 'NAICS', 1897, 62211, 4, 1896, 622110, 5),
(4337, 'NAICS', 144, 2122, 3, 151, 212231, 5),
(4338, 'NAICS', 1554, 525, 2, 1562, 5259, 3),
(4339, 'SIC', 4308, 20, 1, 3003, 2044, 4),
(4340, 'SIC', 3008, 2050, 3, 3009, 2051, 4),
(4341, 'SIC', 4307, 15, 1, 2952, 1622, 4),
(4342, 'SIC', 4308, 20, 1, 3353, 3340, 3),
(4343, 'SIC', 3857, 5620, 3, 3858, 5621, 4),
(4344, 'NAICS', 1812, 61, 1, 1832, 611511, 5),
(4345, 'SIC', 4309, 40, 1, 3644, 4449, 4),
(4346, 'NAICS', 2166, 923, 2, 2172, 923130, 5),
(4347, 'SIC', 2982, 2000, 2, 2992, 2026, 4),
(4348, 'SIC', 3693, 4900, 2, 3702, 4931, 4),
(4349, 'SIC', 3059, 2250, 3, 3061, 2252, 4),
(4350, 'SIC', 4313, 70, 1, 4034, 7251, 4),
(4351, 'NAICS', 1850, 62, 1, 1906, 623110, 5),
(4352, 'NAICS', 2, 111, 2, 6, 111120, 5),
(4353, 'NAICS', 931, 423, 2, 940, 42314, 4),
(4354, 'NAICS', 2053, 81121, 4, 2057, 811219, 5),
(4355, 'NAICS', 2136, 921, 2, 2145, 92114, 4),
(4356, 'SEC', 2355, 3200, 2, 2369, 3281, 4),
(4357, 'SEC', 2791, 20, 1, 2333, 2860, 3),
(4358, 'NAICS', 1813, 611, 2, 1814, 6111, 3),
(4359, 'NAICS', 2, 111, 2, 9, 11113, 4),
(4360, 'NAICS', 930, 42, 1, 1067, 424710, 5),
(4361, 'SEC', 2786, 9720, 3, 2787, 9721, 4),
(4362, 'SIC', 3555, 3820, 3, 3557, 3822, 4),
(4363, 'SIC', 4305, 1, 1, 2881, 921, 4),
(4364, 'SIC', 4310, 50, 1, 3750, 5082, 4),
(4365, 'NAICS', 74, 11233, 4, 73, 112330, 5),
(4366, 'NAICS', 181, 221, 2, 202, 22132, 4),
(4367, 'NAICS', 2020, 722, 2, 2031, 7225, 3),
(4368, 'SIC', 2993, 2030, 3, 2997, 2035, 4),
(4369, 'NAICS', 2, 111, 2, 41, 111421, 5),
(4370, 'NAICS', 1726, 561, 2, 1783, 561790, 5),
(4371, 'NAICS', 1, 11, 1, 86, 112511, 5),
(4372, 'SIC', 3636, 4400, 2, 3653, 4499, 4),
(4373, 'SIC', 4305, 1, 1, 2872, 831, 4),
(4374, 'SIC', 3674, 4740, 3, 3675, 4741, 4),
(4375, 'SIC', 4310, 50, 1, 3786, 5154, 4),
(4376, 'NAICS', 1980, 7131, 3, 1982, 71311, 4),
(4377, 'NAICS', 205, 23, 1, 219, 2371, 3),
(4378, 'NAICS', 1514, 5231, 3, 1519, 523130, 5),
(4379, 'SIC', 4146, 8000, 2, 4166, 8070, 3),
(4380, 'SEC', 2794, 52, 1, 2640, 5900, 2),
(4381, 'SIC', 4308, 20, 1, 3413, 3494, 4),
(4382, 'NAICS', 1942, 71, 1, 1979, 713, 2),
(4383, 'NAICS', 2005, 7211, 3, 2012, 721199, 5),
(4384, 'NAICS', 2135, 92, 1, 2163, 92216, 4),
(4385, 'SEC', 2408, 3530, 3, 2412, 3537, 4),
(4386, 'NAICS', 1725, 56, 1, 1781, 561740, 5),
(4387, 'SIC', 4178, 8200, 2, 4182, 8221, 4),
(4388, 'SIC', 4040, 7300, 2, 4043, 7312, 4),
(4389, 'NAICS', 2182, 925, 2, 2187, 92512, 4),
(4390, 'SIC', 3149, 2510, 3, 3155, 2519, 4),
(4391, 'NAICS', 205, 23, 1, 273, 2389, 3),
(4392, 'SEC', 2302, 2700, 2, 2315, 2770, 3),
(4393, 'NAICS', 1758, 5615, 3, 1763, 56159, 4),
(4394, 'SIC', 3729, 5040, 3, 3732, 5045, 4),
(4395, 'NAICS', 205, 23, 1, 210, 236116, 5),
(4396, 'NAICS', 1480, 52, 1, 1510, 52232, 4),
(4397, 'NAICS', 1979, 713, 2, 1985, 7132, 3),
(4398, 'SEC', 2713, 7300, 2, 2729, 7374, 4),
(4399, 'SIC', 4259, 9220, 3, 4262, 9223, 4),
(4400, 'SEC', 2424, 3570, 3, 2429, 3578, 4),
(4401, 'NAICS', 180, 22, 1, 194, 221122, 5),
(4402, 'SIC', 3804, 5200, 2, 3810, 5251, 4),
(4403, 'NAICS', 1624, 54, 1, 1713, 54193, 4),
(4404, 'NAICS', 167, 21239, 4, 170, 212393, 5),
(4405, 'SIC', 2982, 2000, 2, 3012, 2060, 3),
(4406, 'NAICS', 955, 4234, 3, 969, 42349, 4),
(4407, 'SIC', 3191, 2710, 3, 3192, 2711, 4),
(4408, 'SIC', 4308, 20, 1, 3420, 3510, 3),
(4409, 'SIC', 4308, 20, 1, 3347, 3324, 4),
(4410, 'SIC', 3301, 3200, 2, 3314, 3255, 4),
(4411, 'SIC', 4313, 70, 1, 4183, 8222, 4),
(4412, 'NAICS', 931, 423, 2, 988, 42373, 4),
(4413, 'NAICS', 1657, 5414, 3, 1662, 541430, 5),
(4414, 'SIC', 4308, 20, 1, 3077, 2290, 3),
(4415, 'NAICS', 1020, 42412, 4, 1019, 424120, 5),
(4416, 'SIC', 3992, 6700, 2, 4003, 6792, 4),
(4417, 'SIC', 3854, 5600, 2, 3867, 5690, 3),
(4418, 'NAICS', 1640, 5413, 3, 1650, 54135, 4),
(4419, 'NAICS', 2004, 721, 2, 2019, 72131, 4),
(4420, 'SIC', 4314, 90, 1, 4302, 9900, 2),
(4421, 'NAICS', 1640, 5413, 3, 1655, 541380, 5),
(4422, 'NAICS', 1, 11, 1, 53, 111991, 5),
(4423, 'SEC', 2791, 20, 1, 2349, 3080, 3),
(4424, 'NAICS', 1569, 53, 1, 1600, 53221, 4),
(4425, 'NAICS', 1836, 6116, 3, 1846, 611699, 5),
(4426, 'SEC', 2476, 3800, 2, 2494, 3850, 3),
(4427, 'NAICS', 2037, 81, 1, 2043, 811113, 5),
(4428, 'NAICS', 1625, 541, 2, 1632, 541191, 5),
(4429, 'SIC', 4308, 20, 1, 3374, 3412, 4),
(4430, 'SIC', 4017, 7200, 2, 4028, 7221, 4),
(4431, 'SIC', 3958, 6300, 2, 3964, 6330, 3),
(4432, 'NAICS', 235, 238, 2, 240, 23812, 4),
(4433, 'NAICS', 2027, 72233, 4, 2026, 722330, 5),
(4434, 'SEC', 2792, 40, 1, 2520, 4220, 3),
(4435, 'SIC', 4310, 50, 1, 3766, 5113, 4),
(4436, 'SEC', 2283, 2500, 2, 2289, 2531, 4),
(4437, 'SIC', 3050, 2200, 2, 3068, 2261, 4),
(4438, 'SEC', 2794, 52, 1, 2626, 5650, 3),
(4439, 'SIC', 4308, 20, 1, 3215, 2810, 3),
(4440, 'SIC', 3762, 5100, 2, 3774, 5140, 3),
(4441, 'SIC', 3613, 4140, 3, 3615, 4142, 4),
(4442, 'NAICS', 1851, 621, 2, 1869, 621391, 5),
(4443, 'SEC', 2791, 20, 1, 2343, 3010, 3),
(4444, 'NAICS', 2070, 81149, 4, 2069, 811490, 5),
(4445, 'SIC', 4310, 50, 1, 3802, 5198, 4),
(4446, 'NAICS', 982, 4237, 3, 983, 423710, 5),
(4447, 'SEC', 2659, 6100, 2, 2662, 6140, 3),
(4448, 'SIC', 3419, 3500, 2, 3469, 3581, 4),
(4449, 'SIC', 4109, 7690, 3, 4110, 7692, 4),
(4450, 'NAICS', 2135, 92, 1, 2137, 9211, 3),
(4451, 'SIC', 3496, 3640, 3, 3499, 3644, 4),
(4452, 'SEC', 2796, 70, 1, 4329, 7385, 4),
(4453, 'SIC', 4007, 7000, 2, 4014, 7033, 4),
(4454, 'SEC', 2788, 1, 1, 2213, 800, 2),
(4455, 'SIC', 2825, 200, 2, 2845, 290, 3),
(4456, 'SEC', 2791, 20, 1, 2338, 2910, 3),
(4457, 'SIC', 4308, 20, 1, 3080, 2297, 4),
(4458, 'SIC', 4284, 9600, 2, 4286, 9611, 4),
(4459, 'SIC', 3928, 6060, 3, 3929, 6061, 4),
(4460, 'SIC', 3093, 2330, 3, 3096, 2337, 4),
(4461, 'NAICS', 173, 2131, 3, 178, 213114, 5),
(4462, 'NAICS', 1741, 5614, 3, 1751, 56144, 4),
(4463, 'NAICS', 1859, 6213, 3, 1867, 62134, 4),
(4464, 'SEC', 2791, 20, 1, 2372, 3310, 3),
(4465, 'SEC', 2753, 8000, 2, 2755, 8011, 4),
(4466, 'NAICS', 1015, 424, 2, 1024, 424210, 5),
(4467, 'SIC', 3337, 3300, 2, 3342, 3316, 4),
(4468, 'SIC', 4101, 7620, 3, 4102, 7622, 4),
(4469, 'NAICS', 235, 238, 2, 271, 238390, 5),
(4470, 'NAICS', 1570, 531, 2, 1583, 5313, 3),
(4471, 'SIC', 3715, 5000, 2, 3730, 5043, 4),
(4472, 'SIC', 4252, 9130, 3, 4253, 9131, 4),
(4473, 'NAICS', 1942, 71, 1, 1970, 7121, 3),
(4474, 'NAICS', 2037, 81, 1, 2100, 81293, 4),
(4475, 'SIC', 3124, 2400, 2, 3139, 2448, 4),
(4476, 'SIC', 2982, 2000, 2, 3026, 2080, 3),
(4477, 'NAICS', 1624, 54, 1, 1677, 541614, 5),
(4478, 'NAICS', 1725, 56, 1, 1740, 56133, 4),
(4479, 'SIC', 4308, 20, 1, 3421, 3511, 4),
(4480, 'NAICS', 1798, 5622, 3, 1799, 56221, 4),
(4481, 'NAICS', 930, 42, 1, 985, 423720, 5),
(4482, 'SIC', 3059, 2250, 3, 3065, 2258, 4),
(4483, 'NAICS', 1485, 522, 2, 1498, 522220, 5),
(4484, 'NAICS', 1666, 5415, 3, 1668, 541511, 5),
(4485, 'NAICS', 1774, 5617, 3, 1782, 56174, 4),
(4486, 'NAICS', 2038, 811, 2, 2065, 811420, 5),
(4487, 'SIC', 4312, 60, 1, 3977, 6500, 2),
(4488, 'NAICS', 1689, 5418, 3, 1698, 541850, 5),
(4489, 'NAICS', 1625, 541, 2, 1647, 541340, 5),
(4490, 'NAICS', 1851, 621, 2, 1862, 621320, 5),
(4491, 'SIC', 3115, 2390, 3, 3118, 2393, 4),
(4492, 'NAICS', 1402, 51, 1, 1404, 5111, 3),
(4493, 'NAICS', 930, 42, 1, 993, 42381, 4),
(4494, 'NAICS', 1960, 71131, 4, 1959, 711310, 5),
(4495, 'SEC', 2446, 3660, 3, 2448, 3663, 4),
(4496, 'NAICS', 1, 11, 1, 54, 111992, 5),
(4497, 'NAICS', 1570, 531, 2, 1579, 53119, 4),
(4498, 'SIC', 4256, 9200, 2, 4262, 9223, 4),
(4499, 'NAICS', 67, 11221, 4, 66, 112210, 5),
(4500, 'NAICS', 930, 42, 1, 939, 423140, 5),
(4501, 'NAICS', 1, 11, 1, 103, 113210, 5),
(4502, 'SEC', 2789, 10, 1, 2226, 1382, 4),
(4503, 'SIC', 4040, 7300, 2, 4044, 7313, 4),
(4504, 'SIC', 2825, 200, 2, 2841, 271, 4),
(4505, 'NAICS', 2037, 81, 1, 2089, 81232, 4),
(4506, 'NAICS', 2017, 7213, 3, 2018, 721310, 5),
(4507, 'NAICS', 1726, 561, 2, 1766, 5616, 3),
(4508, 'NAICS', 2037, 81, 1, 2117, 8134, 3),
(4509, 'SIC', 2805, 130, 3, 2809, 134, 4),
(4510, 'NAICS', 1725, 56, 1, 1795, 562111, 5),
(4511, 'SIC', 4308, 20, 1, 3295, 3161, 4),
(4512, 'SIC', 3762, 5100, 2, 3770, 5131, 4),
(4513, 'SIC', 4311, 52, 1, 3820, 5390, 3),
(4514, 'SIC', 3587, 3950, 3, 3590, 3953, 4),
(4515, 'NAICS', 1850, 62, 1, 1890, 62191, 4),
(4516, 'NAICS', 2003, 72, 1, 2027, 72233, 4),
(4517, 'SIC', 2982, 2000, 2, 3027, 2082, 4),
(4518, 'SIC', 3206, 2770, 3, 3207, 2771, 4),
(4519, 'SIC', 4312, 60, 1, 3967, 6351, 4),
(4520, 'SIC', 4311, 52, 1, 3867, 5690, 3),
(4521, 'NAICS', 1431, 5122, 3, 1439, 51224, 4),
(4522, 'SEC', 2793, 50, 1, 2600, 5170, 3),
(4523, 'NAICS', 132, 21, 1, 168, 212391, 5),
(4524, 'NAICS', 236, 2381, 3, 248, 23816, 4),
(4525, 'NAICS', 19, 1112, 3, 21, 111211, 5),
(4526, 'NAICS', 1851, 621, 2, 1860, 621310, 5),
(4527, 'SIC', 3870, 5710, 3, 3872, 5713, 4),
(4528, 'SEC', 2791, 20, 1, 2391, 3440, 3),
(4529, 'SIC', 3124, 2400, 2, 3143, 2452, 4),
(4530, 'NAICS', 2107, 8132, 3, 2110, 813212, 5),
(4531, 'NAICS', 1402, 51, 1, 1430, 512199, 5),
(4532, 'NAICS', 2040, 81111, 4, 2044, 811118, 5),
(4533, 'NAICS', 2135, 92, 1, 2176, 924, 2),
(4534, 'SIC', 4308, 20, 1, 3294, 3160, 3),
(4535, 'SIC', 3419, 3500, 2, 3442, 3548, 4),
(4536, 'NAICS', 172, 213, 2, 174, 21311, 4),
(4537, 'SIC', 3371, 3400, 2, 3401, 3470, 3),
(4538, 'NAICS', 1850, 62, 1, 1895, 6221, 3),
(4539, 'SIC', 3907, 5980, 3, 3909, 5984, 4),
(4540, 'NAICS', 1792, 562, 2, 1806, 56291, 4),
(4541, 'SIC', 3434, 3540, 3, 3436, 3542, 4),
(4542, 'NAICS', 1725, 56, 1, 1792, 562, 2),
(4543, 'NAICS', 2188, 926, 2, 2193, 92612, 4),
(4544, 'NAICS', 1944, 7111, 3, 1950, 71113, 4),
(4545, 'SIC', 3261, 3000, 2, 3281, 3089, 4),
(4546, 'NAICS', 2130, 81399, 4, 2129, 813990, 5),
(4547, 'NAICS', 1480, 52, 1, 1525, 52321, 4),
(4548, 'SIC', 3526, 3700, 2, 3546, 3764, 4),
(4549, 'SIC', 3050, 2200, 2, 3082, 2299, 4),
(4550, 'SIC', 4308, 20, 1, 3466, 3578, 4),
(4551, 'NAICS', 1987, 71321, 4, 1986, 713210, 5),
(4552, 'SIC', 4309, 40, 1, 3674, 4740, 3),
(4553, 'NAICS', 2166, 923, 2, 2167, 9231, 3),
(4554, 'SEC', 2713, 7300, 2, 2717, 7330, 3),
(4555, 'SIC', 4146, 8000, 2, 4170, 8082, 4),
(4556, 'NAICS', 1850, 62, 1, 1916, 623312, 5),
(4557, 'SIC', 4310, 50, 1, 3728, 5039, 4),
(4558, 'SIC', 4113, 7800, 2, 4118, 7822, 4),
(4559, 'NAICS', 1725, 56, 1, 1779, 561730, 5),
(4560, 'NAICS', 1620, 533, 2, 1622, 533110, 5),
(4561, 'SEC', 2791, 20, 1, 2462, 3714, 4),
(4562, 'SIC', 4311, 52, 1, 3817, 5311, 4),
(4563, 'SEC', 2714, 7310, 3, 2715, 7311, 4),
(4564, 'NAICS', 236, 2381, 3, 242, 23813, 4),
(4565, 'SIC', 4146, 8000, 2, 4174, 8099, 4),
(4566, 'NAICS', 138, 212, 2, 160, 212313, 5),
(4567, 'NAICS', 1, 11, 1, 29, 111331, 5),
(4568, 'NAICS', 1624, 54, 1, 1684, 54171, 4),
(4569, 'SEC', 2631, 5710, 3, 2632, 5712, 4),
(4570, 'SIC', 4308, 20, 1, 3186, 2676, 4),
(4571, 'SIC', 4306, 10, 1, 2927, 1446, 4),
(4572, 'SEC', 2539, 4800, 2, 2546, 4832, 4),
(4573, 'SEC', 2793, 50, 1, 2577, 5050, 3),
(4574, 'NAICS', 1583, 5313, 3, 1589, 531390, 5),
(4575, 'SEC', 2738, 7800, 2, 2747, 7841, 4),
(4576, 'SIC', 4298, 9710, 3, 4299, 9711, 4),
(4577, 'NAICS', 156, 2123, 3, 168, 212391, 5),
(4578, 'NAICS', 1569, 53, 1, 1575, 53112, 4),
(4579, 'SEC', 2276, 2400, 2, 2282, 2452, 4),
(4580, 'SIC', 4306, 10, 1, 2902, 1220, 3),
(4581, 'SIC', 3148, 2500, 2, 3151, 2512, 4),
(4582, 'SIC', 3865, 5660, 3, 3866, 5661, 4),
(4583, 'NAICS', 1015, 424, 2, 1086, 42495, 4),
(4584, 'NAICS', 930, 42, 1, 999, 42384, 4),
(4585, 'NAICS', 1537, 5241, 3, 1542, 524126, 5),
(4586, 'NAICS', 2132, 8141, 3, 2133, 814110, 5),
(4587, 'SIC', 4089, 7530, 3, 4096, 7539, 4),
(4588, 'NAICS', 930, 42, 1, 1041, 42443, 4),
(4589, 'NAICS', 1625, 541, 2, 1644, 54132, 4),
(4590, 'SEC', 2677, 6300, 2, 2685, 6350, 3),
(4591, 'SIC', 4186, 8240, 3, 4189, 8249, 4),
(4592, 'NAICS', 1, 11, 1, 3, 1111, 3),
(4593, 'NAICS', 1851, 621, 2, 1856, 6212, 3),
(4594, 'SIC', 3214, 2800, 2, 3229, 2836, 4),
(4595, 'NAICS', 1554, 525, 2, 1557, 52511, 4),
(4596, 'NAICS', 1829, 61143, 4, 1828, 611430, 5),
(4597, 'SIC', 4277, 9500, 2, 4278, 9510, 3),
(4598, 'SIC', 3172, 2630, 3, 3173, 2631, 4),
(4599, 'SIC', 3740, 5060, 3, 3741, 5063, 4),
(4600, 'SEC', 2591, 5100, 2, 2604, 5190, 3),
(4601, 'SIC', 3949, 6210, 3, 3950, 6211, 4),
(4602, 'SIC', 4313, 70, 1, 4186, 8240, 3),
(4603, 'NAICS', 2037, 81, 1, 2106, 81311, 4),
(4604, 'NAICS', 1838, 61161, 4, 1837, 611610, 5),
(4605, 'NAICS', 1480, 52, 1, 1538, 52411, 4),
(4606, 'SIC', 2918, 1400, 2, 2937, 1490, 3),
(4607, 'NAICS', 1402, 51, 1, 1461, 51741, 4),
(4608, 'NAICS', 1665, 54149, 4, 1664, 541490, 5),
(4609, 'SIC', 3272, 3080, 3, 3281, 3089, 4),
(4610, 'NAICS', 1537, 5241, 3, 1546, 52413, 4),
(4611, 'SIC', 3419, 3500, 2, 3456, 3565, 4),
(4612, 'NAICS', 1979, 713, 2, 1980, 7131, 3),
(4613, 'NAICS', 1725, 56, 1, 1729, 56111, 4),
(4614, 'SEC', 2791, 20, 1, 2428, 3577, 4),
(4615, 'SIC', 3103, 2360, 3, 3104, 2361, 4),
(4616, 'SIC', 3269, 3060, 3, 3271, 3069, 4),
(4617, 'NAICS', 1888, 6219, 3, 1893, 621999, 5),
(4618, 'NAICS', 2020, 722, 2, 2026, 722330, 5),
(4619, 'NAICS', 1004, 4239, 3, 1006, 42391, 4),
(4620, 'NAICS', 970, 4235, 3, 972, 42351, 4),
(4621, 'NAICS', 1850, 62, 1, 1852, 6211, 3),
(4622, 'SIC', 3050, 2200, 2, 3054, 2221, 4),
(4623, 'NAICS', 2204, 928, 2, 2205, 9281, 3),
(4624, 'SIC', 4311, 52, 1, 3894, 5941, 4),
(4625, 'NAICS', 255, 23821, 4, 254, 238210, 5),
(4626, 'NAICS', 1774, 5617, 3, 1784, 56179, 4),
(4627, 'SIC', 4308, 20, 1, 3542, 3750, 3),
(4628, 'SIC', 3918, 6010, 3, 3919, 6011, 4),
(4629, 'NAICS', 1480, 52, 1, 1507, 522310, 5),
(4630, 'SEC', 2791, 20, 1, 2486, 3827, 4),
(4631, 'SEC', 2791, 20, 1, 2458, 3700, 2),
(4632, 'SIC', 3106, 2370, 3, 3107, 2371, 4),
(4633, 'SIC', 3633, 4300, 2, 3634, 4310, 3),
(4634, 'SIC', 3371, 3400, 2, 3400, 3469, 4),
(4635, 'SIC', 3762, 5100, 2, 3789, 5162, 4),
(4636, 'NAICS', 1408, 51112, 4, 1407, 511120, 5),
(4637, 'NAICS', 2020, 722, 2, 2024, 722320, 5),
(4638, 'SIC', 3156, 2520, 3, 3158, 2522, 4),
(4639, 'NAICS', 1979, 713, 2, 1993, 713920, 5),
(4640, 'SIC', 4308, 20, 1, 3271, 3069, 4),
(4641, 'NAICS', 260, 2383, 3, 268, 23834, 4),
(4642, 'SEC', 2384, 3400, 2, 2387, 3412, 4),
(4643, 'SIC', 4308, 20, 1, 3046, 2130, 3),
(4644, 'SIC', 4308, 20, 1, 3447, 3554, 4),
(4645, 'SIC', 3809, 5250, 3, 3810, 5251, 4),
(4646, 'SEC', 2659, 6100, 2, 2661, 6111, 4),
(4647, 'SIC', 3576, 3900, 2, 3588, 3951, 4),
(4648, 'SIC', 3520, 3690, 3, 3521, 3691, 4),
(4649, 'NAICS', 1725, 56, 1, 1802, 562213, 5),
(4650, 'SIC', 4313, 70, 1, 4219, 8660, 3),
(4651, 'SIC', 4041, 7310, 3, 4043, 7312, 4),
(4652, 'SEC', 2488, 3840, 3, 2491, 3843, 4),
(4653, 'SEC', 2792, 40, 1, 2525, 4412, 4),
(4654, 'SEC', 2796, 70, 1, 2738, 7800, 2),
(4655, 'SIC', 3837, 5500, 2, 3851, 5571, 4),
(4656, 'SIC', 4120, 7830, 3, 4122, 7833, 4),
(4657, 'NAICS', 218, 237, 2, 234, 23799, 4),
(4658, 'SIC', 4311, 52, 1, 3830, 5441, 4),
(4659, 'NAICS', 2119, 81341, 4, 2118, 813410, 5),
(4660, 'SIC', 3544, 3760, 3, 3547, 3769, 4),
(4661, 'SIC', 3729, 5040, 3, 3730, 5043, 4),
(4662, 'NAICS', 2207, 92811, 4, 2206, 928110, 5),
(4663, 'SIC', 4308, 20, 1, 3007, 2048, 4),
(4664, 'SEC', 2796, 70, 1, 2734, 7389, 4),
(4665, 'SIC', 2825, 200, 2, 2829, 213, 4),
(4666, 'NAICS', 931, 423, 2, 963, 42344, 4),
(4667, 'SEC', 2240, 2000, 2, 2242, 2011, 4),
(4668, 'SIC', 4313, 70, 1, 4111, 7694, 4),
(4669, 'SIC', 4309, 40, 1, 3713, 4970, 3),
(4670, 'SIC', 4192, 8300, 2, 4193, 8320, 3),
(4671, 'SIC', 3797, 5190, 3, 3803, 5199, 4),
(4672, 'NAICS', 1979, 713, 2, 1998, 71394, 4),
(4673, 'NAICS', 1559, 52512, 4, 1558, 525120, 5),
(4674, 'NAICS', 2061, 8114, 3, 2069, 811490, 5),
(4675, 'SIC', 3637, 4410, 3, 3638, 4412, 4),
(4676, 'NAICS', 180, 22, 1, 190, 221117, 5),
(4677, 'SIC', 4307, 15, 1, 2961, 1731, 4),
(4678, 'SIC', 3200, 2750, 3, 3202, 2754, 4),
(4679, 'NAICS', 1076, 4249, 3, 1088, 42499, 4),
(4680, 'SIC', 3167, 2600, 2, 3185, 2675, 4),
(4681, 'SIC', 4308, 20, 1, 3428, 3532, 4),
(4682, 'NAICS', 991, 4238, 3, 998, 423840, 5),
(4683, 'SIC', 4308, 20, 1, 3360, 3356, 4),
(4684, 'SIC', 4310, 50, 1, 3745, 5072, 4),
(4685, 'NAICS', 1469, 51821, 4, 1468, 518210, 5),
(4686, 'NAICS', 1666, 5415, 3, 1667, 54151, 4),
(4687, 'NAICS', 1402, 51, 1, 1413, 51119, 4),
(4688, 'SIC', 4308, 20, 1, 3550, 3795, 4),
(4689, 'SIC', 4040, 7300, 2, 4050, 7331, 4),
(4690, 'SEC', 2662, 6140, 3, 2663, 6141, 4),
(4691, 'SIC', 4015, 7040, 3, 4016, 7041, 4),
(4692, 'SIC', 4313, 70, 1, 4195, 8330, 3),
(4693, 'NAICS', 1431, 5122, 3, 1435, 51222, 4),
(4694, 'SIC', 4310, 50, 1, 3773, 5139, 4),
(4695, 'SIC', 3252, 2900, 2, 3260, 2999, 4),
(4696, 'SIC', 3693, 4900, 2, 3697, 4922, 4),
(4697, 'SIC', 3605, 4100, 2, 3608, 4119, 4),
(4698, 'NAICS', 2039, 8111, 3, 2050, 811192, 5),
(4699, 'NAICS', 1921, 6241, 3, 1924, 624120, 5),
(4700, 'NAICS', 1015, 424, 2, 1037, 42441, 4),
(4701, 'NAICS', 1871, 6214, 3, 1872, 621410, 5),
(4702, 'SEC', 2796, 70, 1, 2774, 8700, 2),
(4703, 'SIC', 3287, 3140, 3, 3288, 3142, 4),
(4704, 'SIC', 2975, 1790, 3, 2980, 1796, 4),
(4705, 'SEC', 2568, 5000, 2, 2572, 5030, 3),
(4706, 'NAICS', 2200, 927, 2, 2201, 9271, 3),
(4707, 'SIC', 3214, 2800, 2, 3242, 2873, 4),
(4708, 'SIC', 3668, 4720, 3, 3670, 4725, 4),
(4709, 'NAICS', 150, 21223, 4, 151, 212231, 5),
(4710, 'SEC', 2791, 20, 1, 2304, 2711, 4),
(4711, 'SEC', 2792, 40, 1, 2529, 4513, 4),
(4712, 'NAICS', 1640, 5413, 3, 1645, 541330, 5),
(4713, 'NAICS', 2135, 92, 1, 2177, 9241, 3),
(4714, 'SIC', 4313, 70, 1, 4136, 7950, 3),
(4715, 'NAICS', 2071, 812, 2, 2099, 812930, 5),
(4716, 'SIC', 2875, 900, 2, 2880, 920, 3),
(4717, 'NAICS', 2177, 9241, 3, 2178, 924110, 5),
(4718, 'SIC', 3917, 6000, 2, 3924, 6029, 4),
(4719, 'SIC', 4312, 60, 1, 3986, 6531, 4),
(4720, 'SIC', 3474, 3590, 3, 3479, 3599, 4),
(4721, 'NAICS', 1813, 611, 2, 1839, 611620, 5),
(4722, 'SIC', 4308, 20, 1, 3314, 3255, 4),
(4723, 'SIC', 3715, 5000, 2, 3732, 5045, 4),
(4724, 'NAICS', 1813, 611, 2, 1815, 611110, 5),
(4725, 'NAICS', 2037, 81, 1, 2069, 811490, 5),
(4726, 'NAICS', 1928, 6242, 3, 1930, 62421, 4),
(4727, 'SEC', 2792, 40, 1, 4317, 4990, 2),
(4728, 'SIC', 4308, 20, 1, 2986, 2015, 4),
(4729, 'SIC', 3167, 2600, 2, 3173, 2631, 4),
(4730, 'SEC', 2630, 5700, 2, 2634, 5731, 4),
(4731, 'SIC', 3355, 3350, 3, 3361, 3357, 4),
(4732, 'NAICS', 931, 423, 2, 951, 423330, 5),
(4733, 'SIC', 3636, 4400, 2, 3647, 4482, 4),
(4734, 'SIC', 4305, 1, 1, 2883, 971, 4),
(4735, 'SIC', 3480, 3600, 2, 3520, 3690, 3),
(4736, 'SEC', 2789, 10, 1, 2215, 1000, 2),
(4737, 'NAICS', 940, 42314, 4, 939, 423140, 5),
(4738, 'NAICS', 2037, 81, 1, 2047, 811122, 5),
(4739, 'SEC', 2240, 2000, 2, 2258, 2092, 4),
(4740, 'SEC', 2403, 3500, 2, 2428, 3577, 4),
(4741, 'NAICS', 1624, 54, 1, 1646, 54133, 4),
(4742, 'NAICS', 1625, 541, 2, 1626, 5411, 3),
(4743, 'SIC', 4313, 70, 1, 4080, 7389, 4),
(4744, 'SIC', 3302, 3210, 3, 3303, 3211, 4),
(4745, 'NAICS', 2136, 921, 2, 2148, 921190, 5),
(4746, 'NAICS', 1402, 51, 1, 1459, 5174, 3),
(4747, 'NAICS', 132, 21, 1, 146, 21221, 4),
(4748, 'NAICS', 930, 42, 1, 1075, 42482, 4),
(4749, 'NAICS', 1851, 621, 2, 1866, 621340, 5),
(4750, 'SIC', 3707, 4950, 3, 3710, 4959, 4),
(4751, 'SIC', 4081, 7500, 2, 4097, 7540, 3),
(4752, 'SIC', 3601, 4000, 2, 3604, 4013, 4),
(4753, 'SIC', 3822, 5400, 2, 3829, 5440, 3),
(4754, 'SEC', 2276, 2400, 2, 2278, 2421, 4),
(4755, 'SEC', 2539, 4800, 2, 2549, 4841, 4),
(4756, 'NAICS', 23, 1113, 3, 29, 111331, 5),
(4757, 'SIC', 4308, 20, 1, 3059, 2250, 3),
(4758, 'SIC', 3831, 5450, 3, 3832, 5451, 4),
(4759, 'NAICS', 132, 21, 1, 158, 212311, 5),
(4760, 'NAICS', 1758, 5615, 3, 1761, 561520, 5),
(4761, 'SIC', 3042, 2110, 3, 3043, 2111, 4),
(4762, 'SIC', 4223, 8700, 2, 4233, 8733, 4),
(4763, 'SEC', 2791, 20, 1, 2255, 2082, 4),
(4764, 'NAICS', 138, 212, 2, 143, 212113, 5),
(4765, 'NAICS', 1486, 5221, 3, 1487, 522110, 5),
(4766, 'NAICS', 3, 1111, 3, 13, 11115, 4),
(4767, 'SIC', 4100, 7600, 2, 4103, 7623, 4),
(4768, 'SIC', 3870, 5710, 3, 3873, 5714, 4),
(4769, 'NAICS', 1812, 61, 1, 1842, 61163, 4),
(4770, 'SIC', 3762, 5100, 2, 3790, 5169, 4),
(4771, 'NAICS', 1480, 52, 1, 1482, 5211, 3),
(4772, 'NAICS', 1850, 62, 1, 1855, 621112, 5),
(4773, 'SIC', 4306, 10, 1, 2896, 1080, 3),
(4774, 'NAICS', 970, 4235, 3, 973, 423520, 5),
(4775, 'SIC', 4312, 60, 1, 3945, 6160, 3),
(4776, 'SIC', 3301, 3200, 2, 3308, 3231, 4),
(4777, 'SIC', 4308, 20, 1, 3233, 2843, 4),
(4778, 'SIC', 3937, 6100, 2, 3941, 6141, 4),
(4779, 'SIC', 3668, 4720, 3, 3671, 4729, 4),
(4780, 'NAICS', 1798, 5622, 3, 1800, 562211, 5),
(4781, 'NAICS', 1463, 51791, 4, 1464, 517911, 5),
(4782, 'SIC', 3167, 2600, 2, 3172, 2630, 3),
(4783, 'NAICS', 2, 111, 2, 44, 111910, 5),
(4784, 'NAICS', 930, 42, 1, 1008, 42392, 4),
(4785, 'SIC', 4308, 20, 1, 3121, 2396, 4),
(4786, 'SIC', 3684, 4820, 3, 3685, 4822, 4),
(4787, 'NAICS', 1725, 56, 1, 1728, 561110, 5),
(4788, 'NAICS', 2037, 81, 1, 2105, 813110, 5),
(4789, 'NAICS', 930, 42, 1, 1059, 424590, 5),
(4790, 'SIC', 4308, 20, 1, 3092, 2329, 4),
(4791, 'SIC', 4308, 20, 1, 3255, 2950, 3),
(4792, 'SEC', 2215, 1000, 2, 2217, 1090, 3),
(4793, 'SEC', 2795, 60, 1, 4325, 6199, 4),
(4794, 'SEC', 2774, 8700, 2, 2778, 8731, 4),
(4795, 'NAICS', 931, 423, 2, 1010, 42393, 4),
(4796, 'NAICS', 132, 21, 1, 164, 212322, 5),
(4797, 'NAICS', 1624, 54, 1, 1638, 541214, 5),
(4798, 'SIC', 4040, 7300, 2, 4077, 7382, 4),
(4799, 'SIC', 3283, 3110, 3, 3284, 3111, 4),
(4800, 'SIC', 3636, 4400, 2, 3652, 4493, 4),
(4801, 'SIC', 3886, 5900, 2, 3895, 5942, 4),
(4802, 'NAICS', 1625, 541, 2, 1657, 5414, 3),
(4803, 'SIC', 3371, 3400, 2, 3373, 3411, 4),
(4804, 'NAICS', 1785, 5619, 3, 1790, 561990, 5),
(4805, 'NAICS', 1943, 711, 2, 1959, 711310, 5),
(4806, 'SIC', 3261, 3000, 2, 3276, 3084, 4),
(4807, 'SIC', 4133, 7940, 3, 4135, 7948, 4),
(4808, 'NAICS', 1537, 5241, 3, 1541, 52412, 4),
(4809, 'SIC', 4306, 10, 1, 2910, 1310, 3),
(4810, 'SIC', 4146, 8000, 2, 4155, 8042, 4),
(4811, 'SEC', 2792, 40, 1, 2530, 4520, 3),
(4812, 'NAICS', 1624, 54, 1, 1660, 541420, 5),
(4813, 'SEC', 2791, 20, 1, 2376, 3330, 3),
(4814, 'SIC', 4308, 20, 1, 3487, 3625, 4),
(4815, 'NAICS', 1419, 512, 2, 1437, 51223, 4),
(4816, 'SIC', 3658, 4520, 3, 3659, 4522, 4),
(4817, 'SIC', 4308, 20, 1, 3152, 2514, 4),
(4818, 'SIC', 4041, 7310, 3, 4044, 7313, 4),
(4819, 'NAICS', 1, 11, 1, 117, 115, 2),
(4820, 'NAICS', 991, 4238, 3, 992, 423810, 5),
(4821, 'NAICS', 1720, 5511, 3, 1722, 551111, 5),
(4822, 'SIC', 4313, 70, 1, 4204, 8410, 3),
(4823, 'SIC', 4310, 50, 1, 3763, 5110, 3),
(4824, 'SIC', 3762, 5100, 2, 3798, 5191, 4),
(4825, 'SIC', 3762, 5100, 2, 3787, 5159, 4),
(4826, 'SIC', 4312, 60, 1, 4000, 6732, 4),
(4827, 'NAICS', 1402, 51, 1, 1406, 51111, 4),
(4828, 'SEC', 2224, 1380, 3, 2226, 1382, 4),
(4829, 'SEC', 2796, 70, 1, 2716, 7320, 3),
(4830, 'NAICS', 133, 211, 2, 134, 2111, 3),
(4831, 'SEC', 2791, 20, 1, 2396, 3450, 3),
(4832, 'SEC', 2640, 5900, 2, 2643, 5940, 3),
(4833, 'NAICS', 1591, 532, 2, 1605, 53229, 4),
(4834, 'NAICS', 1583, 5313, 3, 1585, 531311, 5),
(4835, 'SIC', 2798, 100, 2, 2803, 116, 4),
(4836, 'NAICS', 20, 11121, 4, 22, 111219, 5),
(4837, 'SIC', 3724, 5030, 3, 3728, 5039, 4),
(4838, 'NAICS', 1640, 5413, 3, 1648, 54134, 4),
(4839, 'NAICS', 23, 1113, 3, 30, 111332, 5),
(4840, 'SEC', 2476, 3800, 2, 2487, 3829, 4),
(4841, 'NAICS', 2117, 8134, 3, 2119, 81341, 4),
(4842, 'SEC', 2302, 2700, 2, 2314, 2761, 4),
(4843, 'SEC', 2794, 52, 1, 2605, 5200, 2),
(4844, 'SIC', 3978, 6510, 3, 3981, 6514, 4),
(4845, 'NAICS', 1523, 5232, 3, 1524, 523210, 5),
(4846, 'NAICS', 1850, 62, 1, 1932, 624221, 5),
(4847, 'NAICS', 1850, 62, 1, 1867, 62134, 4),
(4848, 'SIC', 3620, 4200, 2, 3627, 4221, 4),
(4849, 'NAICS', 56, 112, 2, 65, 1122, 3),
(4850, 'NAICS', 930, 42, 1, 978, 423620, 5),
(4851, 'NAICS', 1992, 71391, 4, 1991, 713910, 5),
(4852, 'SIC', 4192, 8300, 2, 4194, 8322, 4),
(4853, 'SIC', 3715, 5000, 2, 3760, 5094, 4),
(4854, 'NAICS', 2135, 92, 1, 2139, 92111, 4),
(4855, 'NAICS', 946, 4233, 3, 948, 42331, 4),
(4856, 'NAICS', 1443, 5151, 3, 1446, 515112, 5),
(4857, 'SEC', 2796, 70, 1, 2756, 8050, 3),
(4858, 'NAICS', 930, 42, 1, 961, 42343, 4),
(4859, 'SIC', 3282, 3100, 2, 3286, 3131, 4),
(4860, 'NAICS', 1624, 54, 1, 1642, 54131, 4),
(4861, 'SIC', 4308, 20, 1, 3489, 3630, 3),
(4862, 'SIC', 3691, 4890, 3, 3692, 4899, 4),
(4863, 'SIC', 4313, 70, 1, 4138, 7952, 4),
(4864, 'NAICS', 1726, 561, 2, 1744, 56142, 4),
(4865, 'SEC', 2494, 3850, 3, 2495, 3851, 4),
(4866, 'NAICS', 1624, 54, 1, 1652, 54136, 4),
(4867, 'NAICS', 117, 115, 2, 123, 115114, 5),
(4868, 'NAICS', 1626, 5411, 3, 1633, 541199, 5),
(4869, 'SEC', 2224, 1380, 3, 2227, 1389, 4),
(4870, 'SIC', 4178, 8200, 2, 4185, 8231, 4),
(4871, 'SIC', 4308, 20, 1, 3392, 3450, 3),
(4872, 'SIC', 4313, 70, 1, 4040, 7300, 2),
(4873, 'SIC', 3193, 2720, 3, 3194, 2721, 4),
(4874, 'NAICS', 1672, 5416, 3, 1675, 541612, 5),
(4875, 'NAICS', 205, 23, 1, 249, 238170, 5),
(4876, 'NAICS', 1625, 541, 2, 1673, 54161, 4),
(4877, 'SIC', 3322, 3270, 3, 3325, 3273, 4),
(4878, 'SIC', 4308, 20, 1, 3555, 3820, 3),
(4879, 'SIC', 3419, 3500, 2, 3464, 3575, 4),
(4880, 'NAICS', 2189, 9261, 3, 2194, 926130, 5),
(4881, 'SIC', 3907, 5980, 3, 3908, 5983, 4),
(4882, 'SIC', 2993, 2030, 3, 2999, 2038, 4),
(4883, 'NAICS', 1088, 42499, 4, 1087, 424990, 5),
(4884, 'SIC', 3292, 3150, 3, 3293, 3151, 4),
(4885, 'SIC', 3214, 2800, 2, 3239, 2865, 4),
(4886, 'NAICS', 1022, 42413, 4, 1021, 424130, 5),
(4887, 'SIC', 4308, 20, 1, 3567, 3843, 4),
(4888, 'NAICS', 2003, 72, 1, 2004, 721, 2),
(4889, 'SIC', 4311, 52, 1, 3837, 5500, 2),
(4890, 'NAICS', 1570, 531, 2, 1576, 531130, 5),
(4891, 'SEC', 2791, 20, 1, 2241, 2010, 3),
(4892, 'SIC', 2799, 110, 3, 2803, 116, 4),
(4893, 'SEC', 2791, 20, 1, 2442, 3640, 3),
(4894, 'NAICS', 2107, 8132, 3, 2111, 813219, 5),
(4895, 'SIC', 2876, 910, 3, 2878, 913, 4),
(4896, 'NAICS', 930, 42, 1, 998, 423840, 5),
(4897, 'SEC', 2792, 40, 1, 2564, 4950, 3),
(4898, 'SIC', 3337, 3300, 2, 3340, 3313, 4),
(4899, 'SIC', 3419, 3500, 2, 3423, 3520, 3),
(4900, 'SEC', 2552, 4900, 2, 4316, 4955, 3),
(4901, 'SIC', 4313, 70, 1, 4165, 8069, 4),
(4902, 'NAICS', 1513, 523, 2, 1518, 52312, 4),
(4903, 'SIC', 4308, 20, 1, 3194, 2721, 4),
(4904, 'NAICS', 986, 42372, 4, 985, 423720, 5),
(4905, 'NAICS', 1907, 62311, 4, 1906, 623110, 5),
(4906, 'SIC', 3371, 3400, 2, 3393, 3451, 4),
(4907, 'SIC', 2875, 900, 2, 2876, 910, 3),
(4908, 'NAICS', 931, 423, 2, 945, 42322, 4),
(4909, 'SEC', 2555, 4920, 3, 2556, 4922, 4),
(4910, 'NAICS', 931, 423, 2, 981, 42369, 4),
(4911, 'SIC', 2983, 2010, 3, 2986, 2015, 4),
(4912, 'SEC', 2725, 7370, 3, 2728, 7373, 4),
(4913, 'NAICS', 1626, 5411, 3, 1629, 541120, 5),
(4914, 'SIC', 4313, 70, 1, 4205, 8412, 4),
(4915, 'SEC', 2794, 52, 1, 4319, 5412, 4),
(4916, 'SIC', 4308, 20, 1, 3333, 3295, 4),
(4917, 'NAICS', 930, 42, 1, 1024, 424210, 5),
(4918, 'NAICS', 1500, 52229, 4, 1504, 522294, 5),
(4919, 'NAICS', 1888, 6219, 3, 1892, 621991, 5),
(4920, 'NAICS', 1045, 42445, 4, 1044, 424450, 5),
(4921, 'SEC', 2791, 20, 1, 2308, 2731, 4),
(4922, 'SEC', 2793, 50, 1, 2570, 5013, 4),
(4923, 'SIC', 3050, 2200, 2, 3081, 2298, 4),
(4924, 'SIC', 3301, 3200, 2, 3328, 3280, 3),
(4925, 'NAICS', 1969, 712, 2, 1974, 71212, 4),
(4926, 'SIC', 3051, 2210, 3, 3052, 2211, 4),
(4927, 'SIC', 4308, 20, 1, 3501, 3646, 4),
(4928, 'SIC', 3419, 3500, 2, 3424, 3523, 4),
(4929, 'NAICS', 1624, 54, 1, 1649, 541350, 5),
(4930, 'SEC', 2434, 3600, 2, 2439, 3621, 4),
(4931, 'NAICS', 991, 4238, 3, 999, 42384, 4),
(4932, 'NAICS', 1403, 511, 2, 1405, 511110, 5),
(4933, 'NAICS', 1416, 5112, 3, 1417, 511210, 5),
(4934, 'SEC', 2791, 20, 1, 2251, 2052, 4),
(4935, 'NAICS', 180, 22, 1, 201, 221320, 5),
(4936, 'NAICS', 205, 23, 1, 260, 2383, 3),
(4937, 'SIC', 4310, 50, 1, 3785, 5153, 4),
(4938, 'NAICS', 205, 23, 1, 224, 237130, 5),
(4939, 'NAICS', 2038, 811, 2, 2043, 811113, 5),
(4940, 'SEC', 2791, 20, 1, 2263, 2210, 3),
(4941, 'SIC', 3337, 3300, 2, 3364, 3364, 4),
(4942, 'SIC', 3953, 6230, 3, 3954, 6231, 4),
(4943, 'NAICS', 1583, 5313, 3, 1586, 531312, 5),
(4944, 'NAICS', 1904, 623, 2, 1914, 62331, 4),
(4945, 'NAICS', 183, 22111, 4, 186, 221113, 5),
(4946, 'SEC', 2791, 20, 1, 2415, 3550, 3),
(4947, 'NAICS', 1663, 54143, 4, 1662, 541430, 5),
(4948, 'SIC', 4310, 50, 1, 3737, 5050, 3),
(4949, 'SIC', 4311, 52, 1, 3824, 5411, 4),
(4950, 'NAICS', 1625, 541, 2, 1691, 54181, 4),
(4951, 'NAICS', 1624, 54, 1, 1694, 541830, 5),
(4952, 'SIC', 3190, 2700, 2, 3194, 2721, 4),
(4953, 'NAICS', 2037, 81, 1, 2065, 811420, 5),
(4954, 'NAICS', 2136, 921, 2, 2149, 92119, 4),
(4955, 'SIC', 4308, 20, 1, 3160, 2531, 4),
(4956, 'SEC', 2319, 2800, 2, 2324, 2833, 4),
(4957, 'SIC', 3987, 6540, 3, 3988, 6541, 4),
(4958, 'SEC', 2500, 3900, 2, 2507, 3944, 4),
(4959, 'SEC', 2610, 5300, 2, 2612, 5311, 4),
(4960, 'NAICS', 1, 11, 1, 70, 11231, 4),
(4961, 'SEC', 2774, 8700, 2, 2779, 8734, 4),
(4962, 'SIC', 4308, 20, 1, 3472, 3586, 4),
(4963, 'SIC', 4311, 52, 1, 3809, 5250, 3),
(4964, 'NAICS', 931, 423, 2, 1012, 42394, 4),
(4965, 'NAICS', 1942, 71, 1, 1957, 711219, 5),
(4966, 'SEC', 2790, 15, 1, 2232, 1531, 4),
(4967, 'SIC', 2884, 1000, 2, 2888, 1021, 4),
(4968, 'SIC', 4311, 52, 1, 3852, 5590, 3),
(4969, 'SIC', 4306, 10, 1, 2900, 1099, 4),
(4970, 'SEC', 2793, 50, 1, 2590, 5099, 4),
(4971, 'NAICS', 1725, 56, 1, 1776, 56171, 4),
(4972, 'SIC', 4308, 20, 1, 3139, 2448, 4),
(4973, 'NAICS', 1008, 42392, 4, 1007, 423920, 5),
(4974, 'NAICS', 1725, 56, 1, 1733, 5613, 3),
(4975, 'SIC', 2982, 2000, 2, 3028, 2083, 4),
(4976, 'SIC', 4311, 52, 1, 3850, 5570, 3),
(4977, 'NAICS', 1402, 51, 1, 1409, 511130, 5),
(4978, 'SEC', 2500, 3900, 2, 2511, 3990, 3),
(4979, 'NAICS', 1623, 53311, 4, 1622, 533110, 5),
(4980, 'SIC', 4308, 20, 1, 3528, 3711, 4),
(4981, 'NAICS', 1, 11, 1, 122, 115113, 5),
(4982, 'NAICS', 205, 23, 1, 231, 23731, 4),
(4983, 'NAICS', 1569, 53, 1, 1611, 53231, 4),
(4984, 'NAICS', 205, 23, 1, 272, 23839, 4),
(4985, 'SIC', 4192, 8300, 2, 4199, 8360, 3),
(4986, 'NAICS', 1942, 71, 1, 1960, 71131, 4),
(4987, 'NAICS', 205, 23, 1, 223, 23712, 4),
(4988, 'SEC', 2791, 20, 1, 2479, 3820, 3),
(4989, 'SIC', 4313, 70, 1, 4054, 7338, 4),
(4990, 'SIC', 2884, 1000, 2, 2898, 1090, 3),
(4991, 'NAICS', 1480, 52, 1, 1559, 52512, 4),
(4992, 'SEC', 2500, 3900, 2, 2504, 3931, 4),
(4993, 'SIC', 3886, 5900, 2, 3892, 5932, 4),
(4994, 'NAICS', 235, 238, 2, 248, 23816, 4),
(4995, 'SIC', 4075, 7380, 3, 4077, 7382, 4),
(4996, 'SIC', 3977, 6500, 2, 3982, 6515, 4),
(4997, 'SIC', 4308, 20, 1, 2995, 2033, 4),
(4998, 'SIC', 4306, 10, 1, 2931, 1470, 3),
(4999, 'NAICS', 1920, 624, 2, 1934, 624230, 5),
(5000, 'NAICS', 1725, 56, 1, 1777, 561720, 5),
(5001, 'NAICS', 1799, 56221, 4, 1800, 562211, 5),
(5002, 'NAICS', 2032, 72251, 4, 2036, 722515, 5),
(5003, 'SIC', 4310, 50, 1, 3799, 5192, 4),
(5004, 'NAICS', 1954, 71121, 4, 1955, 711211, 5),
(5005, 'NAICS', 180, 22, 1, 192, 22112, 4),
(5006, 'SEC', 2796, 70, 1, 2777, 8730, 3),
(5007, 'SIC', 2939, 1500, 2, 2943, 1530, 3),
(5008, 'SIC', 4308, 20, 1, 3076, 2284, 4),
(5009, 'SIC', 3676, 4780, 3, 3677, 4783, 4),
(5010, 'NAICS', 3, 1111, 3, 10, 111140, 5),
(5011, 'SEC', 2303, 2710, 3, 2304, 2711, 4),
(5012, 'NAICS', 1015, 424, 2, 1067, 424710, 5),
(5013, 'SIC', 3686, 4830, 3, 3688, 4833, 4),
(5014, 'SIC', 3050, 2200, 2, 3071, 2270, 3),
(5015, 'SIC', 3127, 2420, 3, 3129, 2426, 4),
(5016, 'SIC', 4017, 7200, 2, 4027, 7220, 3),
(5017, 'SIC', 3041, 2100, 2, 3043, 2111, 4),
(5018, 'SIC', 4040, 7300, 2, 4067, 7372, 4),
(5019, 'NAICS', 931, 423, 2, 971, 423510, 5),
(5020, 'SIC', 2962, 1740, 3, 2963, 1741, 4),
(5021, 'NAICS', 1, 11, 1, 16, 11119, 4),
(5022, 'SEC', 2791, 20, 1, 2439, 3621, 4),
(5023, 'SIC', 4314, 90, 1, 4253, 9131, 4),
(5024, 'NAICS', 1, 11, 1, 30, 111332, 5),
(5025, 'NAICS', 56, 112, 2, 68, 1123, 3),
(5026, 'SEC', 2568, 5000, 2, 2579, 5060, 3),
(5027, 'SIC', 4313, 70, 1, 4084, 7514, 4),
(5028, 'SIC', 2798, 100, 2, 2812, 161, 4),
(5029, 'NAICS', 1823, 6114, 3, 1829, 61143, 4),
(5030, 'NAICS', 931, 423, 2, 975, 4236, 3),
(5031, 'NAICS', 1720, 5511, 3, 1724, 551114, 5),
(5032, 'SIC', 4308, 20, 1, 3398, 3465, 4),
(5033, 'NAICS', 1419, 512, 2, 1427, 512132, 5),
(5034, 'NAICS', 2003, 72, 1, 2021, 7223, 3),
(5035, 'NAICS', 930, 42, 1, 992, 423810, 5),
(5036, 'NAICS', 1812, 61, 1, 1816, 61111, 4),
(5037, 'NAICS', 2135, 92, 1, 2161, 92215, 4),
(5038, 'SIC', 4314, 90, 1, 4272, 9431, 4),
(5039, 'NAICS', 2061, 8114, 3, 2065, 811420, 5),
(5040, 'SEC', 2791, 20, 1, 2353, 3100, 2),
(5041, 'SIC', 3837, 5500, 2, 3849, 5561, 4),
(5042, 'SIC', 3693, 4900, 2, 3694, 4910, 3),
(5043, 'SIC', 3337, 3300, 2, 3339, 3312, 4),
(5044, 'NAICS', 118, 1151, 3, 123, 115114, 5),
(5045, 'SEC', 2795, 60, 1, 2704, 6790, 3),
(5046, 'SIC', 3552, 3800, 2, 3566, 3842, 4),
(5047, 'NAICS', 1953, 7112, 3, 1957, 711219, 5),
(5048, 'NAICS', 236, 2381, 3, 240, 23812, 4),
(5049, 'NAICS', 1689, 5418, 3, 1691, 54181, 4),
(5050, 'NAICS', 1726, 561, 2, 1771, 56162, 4),
(5051, 'SIC', 3877, 5730, 3, 3880, 5735, 4),
(5052, 'SIC', 3606, 4110, 3, 3608, 4119, 4),
(5053, 'NAICS', 2151, 9221, 3, 2159, 92214, 4),
(5054, 'SEC', 2446, 3660, 3, 2449, 3669, 4),
(5055, 'NAICS', 1480, 52, 1, 1563, 525910, 5),
(5056, 'NAICS', 1851, 621, 2, 1882, 62151, 4),
(5057, 'NAICS', 2039, 8111, 3, 2049, 811191, 5),
(5058, 'SEC', 2791, 20, 1, 2384, 3400, 2),
(5059, 'SIC', 4308, 20, 1, 3217, 2813, 4),
(5060, 'SIC', 3246, 2890, 3, 3251, 2899, 4),
(5061, 'NAICS', 1001, 42385, 4, 1000, 423850, 5),
(5062, 'SEC', 2434, 3600, 2, 2442, 3640, 3),
(5063, 'SIC', 3282, 3100, 2, 3295, 3161, 4),
(5064, 'SEC', 2476, 3800, 2, 2482, 3823, 4),
(5065, 'SEC', 2792, 40, 1, 2512, 4000, 2),
(5066, 'NAICS', 1792, 562, 2, 1795, 562111, 5),
(5067, 'SIC', 3480, 3600, 2, 3505, 3651, 4),
(5068, 'SEC', 2792, 40, 1, 2560, 4931, 4),
(5069, 'NAICS', 231, 23731, 4, 230, 237310, 5),
(5070, 'NAICS', 1851, 621, 2, 1881, 6215, 3),
(5071, 'NAICS', 2038, 811, 2, 2041, 811111, 5),
(5072, 'NAICS', 1793, 5621, 3, 1797, 562119, 5),
(5073, 'SIC', 4307, 15, 1, 2942, 1522, 4),
(5074, 'SIC', 2875, 900, 2, 2878, 913, 4),
(5075, 'NAICS', 1035, 4244, 3, 1050, 424480, 5),
(5076, 'SEC', 2476, 3800, 2, 2492, 3844, 4),
(5077, 'SEC', 2649, 6000, 2, 2654, 6030, 3),
(5078, 'SIC', 3419, 3500, 2, 3437, 3543, 4),
(5079, 'SIC', 4136, 7950, 3, 4137, 7951, 4),
(5080, 'SIC', 3713, 4970, 3, 3714, 4971, 4),
(5081, 'NAICS', 181, 221, 2, 198, 2213, 3),
(5082, 'SIC', 3605, 4100, 2, 3611, 4130, 3),
(5083, 'SIC', 3282, 3100, 2, 3294, 3160, 3),
(5084, 'NAICS', 68, 1123, 3, 77, 112390, 5),
(5085, 'NAICS', 2039, 8111, 3, 2040, 81111, 4),
(5086, 'SIC', 2798, 100, 2, 2807, 132, 4),
(5087, 'SIC', 2918, 1400, 2, 2938, 1499, 4),
(5088, 'SEC', 2795, 60, 1, 2705, 6792, 4),
(5089, 'SIC', 3451, 3560, 3, 3455, 3564, 4),
(5090, 'NAICS', 1, 11, 1, 105, 1133, 3),
(5091, 'SEC', 2280, 2450, 3, 2281, 2451, 4),
(5092, 'SIC', 4308, 20, 1, 3143, 2452, 4),
(5093, 'SEC', 2791, 20, 1, 2355, 3200, 2),
(5094, 'SIC', 4310, 50, 1, 3755, 5088, 4),
(5095, 'NAICS', 2103, 813, 2, 2129, 813990, 5),
(5096, 'SEC', 2791, 20, 1, 2306, 2721, 4),
(5097, 'NAICS', 1550, 52429, 4, 1552, 524292, 5),
(5098, 'NAICS', 2205, 9281, 3, 2207, 92811, 4),
(5099, 'SEC', 2250, 2050, 3, 2251, 2052, 4),
(5100, 'SIC', 2945, 1540, 3, 2947, 1542, 4),
(5101, 'NAICS', 182, 2211, 3, 187, 221114, 5),
(5102, 'SIC', 3620, 4200, 2, 3623, 4213, 4),
(5103, 'NAICS', 1, 11, 1, 8, 111130, 5),
(5104, 'SEC', 2403, 3500, 2, 2415, 3550, 3),
(5105, 'NAICS', 156, 2123, 3, 160, 212313, 5),
(5106, 'NAICS', 138, 212, 2, 168, 212391, 5),
(5107, 'NAICS', 1725, 56, 1, 1806, 56291, 4),
(5108, 'SIC', 4113, 7800, 2, 4119, 7829, 4),
(5109, 'NAICS', 206, 236, 2, 213, 2362, 3),
(5110, 'SIC', 3715, 5000, 2, 3758, 5092, 4),
(5111, 'SIC', 2855, 740, 3, 2856, 741, 4),
(5112, 'NAICS', 232, 2379, 3, 234, 23799, 4),
(5113, 'NAICS', 2200, 927, 2, 2203, 92711, 4),
(5114, 'SIC', 4308, 20, 1, 3422, 3519, 4),
(5115, 'NAICS', 1969, 712, 2, 1975, 712130, 5),
(5116, 'NAICS', 2149, 92119, 4, 2148, 921190, 5),
(5117, 'SEC', 2791, 20, 1, 2389, 3430, 3),
(5118, 'NAICS', 1928, 6242, 3, 1929, 624210, 5),
(5119, 'NAICS', 1921, 6241, 3, 1927, 62419, 4),
(5120, 'NAICS', 1760, 56151, 4, 1759, 561510, 5),
(5121, 'SIC', 4305, 1, 1, 2815, 172, 4),
(5122, 'SIC', 3504, 3650, 3, 3506, 3652, 4),
(5123, 'NAICS', 1598, 5322, 3, 1600, 53221, 4),
(5124, 'NAICS', 2135, 92, 1, 2192, 926120, 5),
(5125, 'NAICS', 1657, 5414, 3, 1659, 54141, 4),
(5126, 'SIC', 4309, 40, 1, 3687, 4832, 4),
(5127, 'SIC', 4312, 60, 1, 3971, 6371, 4),
(5128, 'NAICS', 235, 238, 2, 263, 238320, 5),
(5129, 'SIC', 3951, 6220, 3, 3952, 6221, 4),
(5130, 'NAICS', 1852, 6211, 3, 1855, 621112, 5),
(5131, 'NAICS', 172, 213, 2, 177, 213113, 5),
(5132, 'SIC', 2982, 2000, 2, 3000, 2040, 3),
(5133, 'NAICS', 1743, 56141, 4, 1742, 561410, 5),
(5134, 'NAICS', 205, 23, 1, 270, 23835, 4),
(5135, 'SIC', 4308, 20, 1, 3020, 2070, 3),
(5136, 'NAICS', 1573, 53111, 4, 1572, 531110, 5),
(5137, 'SIC', 4208, 8600, 2, 4221, 8690, 3),
(5138, 'SEC', 2591, 5100, 2, 2592, 5110, 3),
(5139, 'SIC', 3552, 3800, 2, 3567, 3843, 4),
(5140, 'SIC', 4171, 8090, 3, 4174, 8099, 4),
(5141, 'SIC', 4040, 7300, 2, 4059, 7352, 4),
(5142, 'NAICS', 2, 111, 2, 5, 11111, 4),
(5143, 'NAICS', 991, 4238, 3, 997, 42383, 4),
(5144, 'SEC', 2458, 3700, 2, 2464, 3716, 4),
(5145, 'SIC', 4308, 20, 1, 3084, 2310, 3),
(5146, 'SIC', 4146, 8000, 2, 4165, 8069, 4),
(5147, 'NAICS', 2040, 81111, 4, 2043, 811113, 5),
(5148, 'SIC', 3601, 4000, 2, 3602, 4010, 3),
(5149, 'SIC', 3576, 3900, 2, 3592, 3960, 3),
(5150, 'SIC', 4308, 20, 1, 3523, 3694, 4),
(5151, 'SIC', 3693, 4900, 2, 3714, 4971, 4),
(5152, 'NAICS', 1812, 61, 1, 1846, 611699, 5),
(5153, 'NAICS', 1904, 623, 2, 1916, 623312, 5),
(5154, 'SIC', 3762, 5100, 2, 3777, 5143, 4),
(5155, 'SEC', 2791, 20, 1, 2262, 2200, 2),
(5156, 'NAICS', 57, 1121, 3, 61, 112120, 5),
(5157, 'SIC', 2958, 1720, 3, 2959, 1721, 4),
(5158, 'SIC', 4308, 20, 1, 3156, 2520, 3),
(5159, 'SEC', 2424, 3570, 3, 2427, 3575, 4),
(5160, 'SIC', 4311, 52, 1, 3836, 5499, 4),
(5161, 'NAICS', 2004, 721, 2, 2016, 721214, 5),
(5162, 'NAICS', 1624, 54, 1, 1672, 5416, 3),
(5163, 'SEC', 2791, 20, 1, 2412, 3537, 4),
(5164, 'SIC', 3301, 3200, 2, 3320, 3264, 4),
(5165, 'NAICS', 1624, 54, 1, 1674, 541611, 5),
(5166, 'SIC', 3337, 3300, 2, 3349, 3330, 3),
(5167, 'SIC', 4309, 40, 1, 3660, 4580, 3),
(5168, 'SEC', 2791, 20, 1, 2467, 3724, 4),
(5169, 'SIC', 4308, 20, 1, 3094, 2331, 4),
(5170, 'SIC', 4308, 20, 1, 3153, 2515, 4),
(5171, 'SIC', 3149, 2510, 3, 3151, 2512, 4),
(5172, 'SIC', 4308, 20, 1, 3043, 2111, 4),
(5173, 'SIC', 4259, 9220, 3, 4264, 9229, 4),
(5174, 'SIC', 4223, 8700, 2, 4231, 8731, 4),
(5175, 'SEC', 2791, 20, 1, 2281, 2451, 4),
(5176, 'NAICS', 105, 1133, 3, 107, 11331, 4),
(5177, 'NAICS', 99, 1131, 3, 100, 113110, 5),
(5178, 'SIC', 4017, 7200, 2, 4023, 7216, 4),
(5179, 'SIC', 4308, 20, 1, 3369, 3398, 4),
(5180, 'NAICS', 1851, 621, 2, 1876, 62149, 4),
(5181, 'SIC', 4314, 90, 1, 4285, 9610, 3),
(5182, 'NAICS', 1970, 7121, 3, 1974, 71212, 4),
(5183, 'SIC', 4308, 20, 1, 3106, 2370, 3),
(5184, 'SIC', 4308, 20, 1, 3552, 3800, 2),
(5185, 'NAICS', 65, 1122, 3, 67, 11221, 4),
(5186, 'NAICS', 930, 42, 1, 949, 423320, 5),
(5187, 'NAICS', 1630, 54112, 4, 1629, 541120, 5),
(5188, 'NAICS', 1861, 62131, 4, 1860, 621310, 5),
(5189, 'SIC', 2918, 1400, 2, 2924, 1429, 4),
(5190, 'NAICS', 2, 111, 2, 26, 111320, 5),
(5191, 'NAICS', 2188, 926, 2, 2189, 9261, 3),
(5192, 'SIC', 3552, 3800, 2, 3555, 3820, 3),
(5193, 'SIC', 3214, 2800, 2, 3245, 2879, 4),
(5194, 'SIC', 3788, 5160, 3, 3789, 5162, 4),
(5195, 'NAICS', 235, 238, 2, 277, 23899, 4),
(5196, 'NAICS', 1624, 54, 1, 1628, 54111, 4),
(5197, 'SIC', 4208, 8600, 2, 4218, 8651, 4),
(5198, 'NAICS', 1771, 56162, 4, 1773, 561622, 5),
(5199, 'NAICS', 1850, 62, 1, 1877, 621491, 5),
(5200, 'NAICS', 2135, 92, 1, 2183, 9251, 3),
(5201, 'NAICS', 1725, 56, 1, 1797, 562119, 5),
(5202, 'SEC', 2606, 5210, 3, 2607, 5211, 4),
(5203, 'NAICS', 1403, 511, 2, 1415, 511199, 5),
(5204, 'NAICS', 1419, 512, 2, 1423, 512120, 5),
(5205, 'SIC', 3804, 5200, 2, 3814, 5271, 4),
(5206, 'SIC', 4081, 7500, 2, 4093, 7536, 4),
(5207, 'NAICS', 1526, 5239, 3, 1527, 523910, 5),
(5208, 'NAICS', 1935, 62423, 4, 1934, 624230, 5),
(5209, 'NAICS', 2135, 92, 1, 2179, 92411, 4),
(5210, 'SIC', 3480, 3600, 2, 3521, 3691, 4),
(5211, 'SIC', 3480, 3600, 2, 3496, 3640, 3),
(5212, 'SIC', 4311, 52, 1, 3879, 5734, 4),
(5213, 'SIC', 3822, 5400, 2, 3823, 5410, 3),
(5214, 'NAICS', 975, 4236, 3, 980, 423690, 5),
(5215, 'SEC', 2791, 20, 1, 2394, 3444, 4),
(5216, 'NAICS', 1419, 512, 2, 1440, 512290, 5),
(5217, 'NAICS', 1538, 52411, 4, 1540, 524114, 5),
(5218, 'NAICS', 56, 112, 2, 60, 112112, 5),
(5219, 'NAICS', 1894, 622, 2, 1899, 622210, 5),
(5220, 'SIC', 4113, 7800, 2, 4121, 7832, 4),
(5221, 'NAICS', 1850, 62, 1, 1873, 62141, 4),
(5222, 'SIC', 3882, 5800, 2, 3885, 5813, 4),
(5223, 'SEC', 2791, 20, 1, 2382, 3360, 3),
(5224, 'SIC', 3636, 4400, 2, 3649, 4490, 3),
(5225, 'NAICS', 1053, 42449, 4, 1052, 424490, 5),
(5226, 'NAICS', 2003, 72, 1, 2011, 721191, 5),
(5227, 'NAICS', 2038, 811, 2, 2070, 81149, 4),
(5228, 'NAICS', 1624, 54, 1, 1692, 541820, 5),
(5229, 'SIC', 3715, 5000, 2, 3722, 5021, 4),
(5230, 'SIC', 3033, 2090, 3, 3039, 2098, 4),
(5231, 'NAICS', 2188, 926, 2, 2198, 926150, 5),
(5232, 'NAICS', 1625, 541, 2, 1687, 541720, 5),
(5233, 'NAICS', 1, 11, 1, 24, 111310, 5),
(5234, 'SIC', 4305, 1, 1, 2860, 752, 4),
(5235, 'NAICS', 2005, 7211, 3, 2010, 72119, 4),
(5236, 'SEC', 2517, 4200, 2, 2518, 4210, 3),
(5237, 'NAICS', 1, 11, 1, 89, 1129, 3),
(5238, 'NAICS', 1569, 53, 1, 1623, 53311, 4),
(5239, 'NAICS', 2103, 813, 2, 2122, 81391, 4),
(5240, 'SIC', 4308, 20, 1, 3587, 3950, 3),
(5241, 'NAICS', 1, 11, 1, 72, 11232, 4),
(5242, 'NAICS', 931, 423, 2, 995, 42382, 4),
(5243, 'NAICS', 1486, 5221, 3, 1493, 522190, 5),
(5244, 'SEC', 2794, 52, 1, 2609, 5271, 4),
(5245, 'SIC', 4308, 20, 1, 3266, 3050, 3),
(5246, 'SIC', 4223, 8700, 2, 4229, 8721, 4),
(5247, 'SEC', 2794, 52, 1, 2638, 5810, 3),
(5248, 'NAICS', 1, 11, 1, 32, 111334, 5),
(5249, 'NAICS', 1035, 4244, 3, 1052, 424490, 5),
(5250, 'SIC', 4306, 10, 1, 2911, 1311, 4),
(5251, 'SIC', 4100, 7600, 2, 4109, 7690, 3),
(5252, 'NAICS', 991, 4238, 3, 996, 423830, 5),
(5253, 'SIC', 4308, 20, 1, 3362, 3360, 3),
(5254, 'NAICS', 205, 23, 1, 261, 238310, 5),
(5255, 'NAICS', 2037, 81, 1, 2044, 811118, 5),
(5256, 'SIC', 3636, 4400, 2, 3651, 4492, 4),
(5257, 'SIC', 3978, 6510, 3, 3980, 6513, 4),
(5258, 'SEC', 2695, 6510, 3, 2698, 6519, 4),
(5259, 'SEC', 2371, 3300, 2, 2380, 3350, 3),
(5260, 'NAICS', 174, 21311, 4, 178, 213114, 5),
(5261, 'NAICS', 1990, 7139, 3, 2002, 71399, 4),
(5262, 'NAICS', 1602, 53222, 4, 1601, 532220, 5),
(5263, 'NAICS', 2103, 813, 2, 2118, 813410, 5),
(5264, 'SIC', 4281, 9530, 3, 4283, 9532, 4),
(5265, 'SIC', 2935, 1480, 3, 2936, 1481, 4),
(5266, 'NAICS', 2120, 8139, 3, 2126, 81393, 4),
(5267, 'SIC', 3108, 2380, 3, 3111, 2385, 4),
(5268, 'SIC', 4081, 7500, 2, 4092, 7534, 4),
(5269, 'SIC', 4308, 20, 1, 3375, 3420, 3),
(5270, 'NAICS', 1624, 54, 1, 1627, 541110, 5),
(5271, 'SEC', 2703, 6700, 2, 2708, 6799, 4),
(5272, 'NAICS', 205, 23, 1, 213, 2362, 3),
(5273, 'NAICS', 1725, 56, 1, 1773, 561622, 5),
(5274, 'NAICS', 2052, 8112, 3, 2055, 811212, 5),
(5275, 'SEC', 2796, 70, 1, 2719, 7340, 3),
(5276, 'NAICS', 930, 42, 1, 1006, 42391, 4),
(5277, 'SEC', 2434, 3600, 2, 2441, 3634, 4),
(5278, 'SIC', 3301, 3200, 2, 3307, 3230, 3),
(5279, 'NAICS', 140, 21211, 4, 142, 212112, 5),
(5280, 'NAICS', 2100, 81293, 4, 2099, 812930, 5),
(5281, 'SIC', 4082, 7510, 3, 4085, 7515, 4),
(5282, 'SEC', 2795, 60, 1, 4328, 6795, 4),
(5283, 'SIC', 4308, 20, 1, 3382, 3432, 4),
(5284, 'SIC', 4018, 7210, 3, 4025, 7218, 4),
(5285, 'SIC', 4089, 7530, 3, 4094, 7537, 4),
(5286, 'NAICS', 51, 11194, 4, 50, 111940, 5),
(5287, 'NAICS', 2040, 81111, 4, 2041, 811111, 5),
(5288, 'SIC', 3246, 2890, 3, 3248, 2892, 4),
(5289, 'SEC', 2792, 40, 1, 2555, 4920, 3),
(5290, 'NAICS', 1970, 7121, 3, 1975, 712130, 5),
(5291, 'NAICS', 1070, 42472, 4, 1069, 424720, 5),
(5292, 'NAICS', 930, 42, 1, 1031, 424330, 5),
(5293, 'SIC', 2855, 740, 3, 2857, 742, 4),
(5294, 'NAICS', 1480, 52, 1, 1555, 5251, 3),
(5295, 'NAICS', 132, 21, 1, 141, 212111, 5),
(5296, 'NAICS', 1726, 561, 2, 1761, 561520, 5),
(5297, 'SIC', 4311, 52, 1, 3821, 5399, 4),
(5298, 'NAICS', 1090, 4251, 3, 1092, 42511, 4),
(5299, 'SIC', 4256, 9200, 2, 4264, 9229, 4),
(5300, 'SIC', 4284, 9600, 2, 4295, 9660, 3),
(5301, 'NAICS', 208, 23611, 4, 209, 236115, 5),
(5302, 'SEC', 2791, 20, 1, 2249, 2040, 3),
(5303, 'SEC', 2403, 3500, 2, 2412, 3537, 4),
(5304, 'NAICS', 144, 2122, 3, 150, 21223, 4),
(5305, 'SEC', 2532, 4580, 3, 2533, 4581, 4),
(5306, 'NAICS', 1725, 56, 1, 1762, 56152, 4),
(5307, 'SEC', 2791, 20, 1, 2341, 2990, 3),
(5308, 'SIC', 4314, 90, 1, 4263, 9224, 4),
(5309, 'SEC', 2791, 20, 1, 2441, 3634, 4),
(5310, 'SIC', 4247, 9100, 2, 4248, 9110, 3),
(5311, 'SIC', 4308, 20, 1, 3002, 2043, 4),
(5312, 'NAICS', 56, 112, 2, 62, 11212, 4),
(5313, 'SIC', 3204, 2760, 3, 3205, 2761, 4),
(5314, 'NAICS', 930, 42, 1, 954, 42339, 4),
(5315, 'SIC', 3384, 3440, 3, 3387, 3443, 4),
(5316, 'SIC', 3337, 3300, 2, 3348, 3325, 4),
(5317, 'NAICS', 1579, 53119, 4, 1578, 531190, 5),
(5318, 'NAICS', 1850, 62, 1, 1899, 622210, 5),
(5319, 'SEC', 2792, 40, 1, 2567, 4961, 4),
(5320, 'SIC', 2937, 1490, 3, 2938, 1499, 4),
(5321, 'SIC', 4308, 20, 1, 3430, 3534, 4),
(5322, 'SIC', 3526, 3700, 2, 3537, 3730, 3),
(5323, 'NAICS', 1942, 71, 1, 1989, 71329, 4),
(5324, 'NAICS', 1725, 56, 1, 1775, 561710, 5),
(5325, 'SIC', 2798, 100, 2, 2815, 172, 4),
(5326, 'NAICS', 1904, 623, 2, 1906, 623110, 5),
(5327, 'SEC', 2384, 3400, 2, 2397, 3451, 4),
(5328, 'NAICS', 205, 23, 1, 233, 237990, 5),
(5329, 'NAICS', 1402, 51, 1, 1412, 51114, 4),
(5330, 'SEC', 2488, 3840, 3, 2493, 3845, 4),
(5331, 'SIC', 2885, 1010, 3, 2886, 1011, 4),
(5332, 'NAICS', 205, 23, 1, 253, 2382, 3),
(5333, 'SIC', 3046, 2130, 3, 3047, 2131, 4),
(5334, 'SIC', 4040, 7300, 2, 4057, 7349, 4),
(5335, 'NAICS', 1917, 6239, 3, 1919, 62399, 4),
(5336, 'SIC', 3788, 5160, 3, 3790, 5169, 4),
(5337, 'SIC', 3605, 4100, 2, 3609, 4120, 3),
(5338, 'SIC', 3715, 5000, 2, 3721, 5020, 3),
(5339, 'NAICS', 1513, 523, 2, 1534, 523991, 5),
(5340, 'SIC', 4312, 60, 1, 3964, 6330, 3),
(5341, 'SIC', 2847, 700, 2, 2853, 723, 4),
(5342, 'NAICS', 43, 1119, 3, 54, 111992, 5),
(5343, 'NAICS', 213, 2362, 3, 214, 236210, 5),
(5344, 'NAICS', 1624, 54, 1, 1707, 541910, 5),
(5345, 'SIC', 3869, 5700, 2, 3881, 5736, 4),
(5346, 'SIC', 4305, 1, 1, 2807, 132, 4),
(5347, 'NAICS', 1624, 54, 1, 1630, 54112, 4),
(5348, 'SIC', 3337, 3300, 2, 3365, 3365, 4),
(5349, 'NAICS', 1812, 61, 1, 1825, 61141, 4),
(5350, 'SEC', 2794, 52, 1, 2619, 5411, 4),
(5351, 'SIC', 3337, 3300, 2, 3357, 3353, 4),
(5352, 'NAICS', 28, 11133, 4, 34, 111336, 5),
(5353, 'SIC', 4308, 20, 1, 3435, 3541, 4),
(5354, 'SIC', 4311, 52, 1, 3878, 5731, 4),
(5355, 'NAICS', 1920, 624, 2, 1937, 624310, 5),
(5356, 'SEC', 2262, 2200, 2, 2268, 2253, 4),
(5357, 'SIC', 2982, 2000, 2, 3016, 2064, 4),
(5358, 'NAICS', 1, 11, 1, 112, 114112, 5),
(5359, 'SIC', 3572, 3860, 3, 3573, 3861, 4),
(5360, 'SIC', 3886, 5900, 2, 3889, 5920, 3),
(5361, 'SEC', 2793, 50, 1, 2585, 5080, 3),
(5362, 'SIC', 3401, 3470, 3, 3402, 3471, 4),
(5363, 'SIC', 3355, 3350, 3, 3356, 3351, 4),
(5364, 'NAICS', 931, 423, 2, 974, 42352, 4),
(5365, 'SIC', 3715, 5000, 2, 3740, 5060, 3),
(5366, 'NAICS', 1850, 62, 1, 1930, 62421, 4),
(5367, 'SEC', 2292, 2600, 2, 2301, 2673, 4),
(5368, 'SIC', 3925, 6030, 3, 3927, 6036, 4),
(5369, 'NAICS', 23, 1113, 3, 32, 111334, 5),
(5370, 'SIC', 4308, 20, 1, 3176, 2653, 4),
(5371, 'NAICS', 1015, 424, 2, 1062, 424610, 5),
(5372, 'SEC', 2701, 6550, 3, 2702, 6552, 4),
(5373, 'SIC', 2914, 1380, 3, 2915, 1381, 4),
(5374, 'SIC', 4308, 20, 1, 3499, 3644, 4),
(5375, 'NAICS', 236, 2381, 3, 238, 23811, 4),
(5376, 'SIC', 2901, 1200, 2, 2905, 1230, 3),
(5377, 'NAICS', 2103, 813, 2, 2124, 81392, 4),
(5378, 'SIC', 3526, 3700, 2, 3540, 3740, 3),
(5379, 'SIC', 3131, 2430, 3, 3135, 2436, 4),
(5380, 'NAICS', 1026, 4243, 3, 1030, 42432, 4),
(5381, 'SIC', 4308, 20, 1, 3531, 3715, 4),
(5382, 'NAICS', 2135, 92, 1, 2165, 92219, 4),
(5383, 'SIC', 4310, 50, 1, 3768, 5122, 4),
(5384, 'NAICS', 1644, 54132, 4, 1643, 541320, 5),
(5385, 'SIC', 3749, 5080, 3, 3755, 5088, 4),
(5386, 'NAICS', 2135, 92, 1, 2169, 92311, 4),
(5387, 'SIC', 3654, 4500, 2, 3660, 4580, 3),
(5388, 'NAICS', 253, 2382, 3, 254, 238210, 5),
(5389, 'NAICS', 1004, 4239, 3, 1008, 42392, 4),
(5390, 'SIC', 4308, 20, 1, 3409, 3490, 3),
(5391, 'SIC', 3958, 6300, 2, 3967, 6351, 4),
(5392, 'NAICS', 97, 11299, 4, 96, 112990, 5),
(5393, 'NAICS', 23, 1113, 3, 24, 111310, 5),
(5394, 'SEC', 2405, 3520, 3, 2406, 3523, 4),
(5395, 'NAICS', 1612, 5324, 3, 1614, 532411, 5),
(5396, 'SIC', 4308, 20, 1, 3133, 2434, 4),
(5397, 'NAICS', 1, 11, 1, 102, 1132, 3),
(5398, 'NAICS', 1850, 62, 1, 1941, 62441, 4),
(5399, 'SIC', 4308, 20, 1, 3566, 3842, 4),
(5400, 'SIC', 4305, 1, 1, 2812, 161, 4),
(5401, 'NAICS', 930, 42, 1, 1033, 424340, 5),
(5402, 'NAICS', 1035, 4244, 3, 1047, 42446, 4),
(5403, 'SEC', 2337, 2900, 2, 2339, 2911, 4),
(5404, 'SIC', 3214, 2800, 2, 3238, 2861, 4),
(5405, 'SIC', 3917, 6000, 2, 3932, 6081, 4),
(5406, 'NAICS', 931, 423, 2, 937, 423130, 5),
(5407, 'NAICS', 931, 423, 2, 935, 423120, 5),
(5408, 'SIC', 4208, 8600, 2, 4222, 8699, 4),
(5409, 'NAICS', 1480, 52, 1, 1552, 524292, 5),
(5410, 'NAICS', 930, 42, 1, 1019, 424120, 5),
(5411, 'SEC', 2476, 3800, 2, 2497, 3861, 4),
(5412, 'NAICS', 1624, 54, 1, 1699, 54185, 4),
(5413, 'NAICS', 43, 1119, 3, 53, 111991, 5),
(5414, 'SIC', 3316, 3260, 3, 3319, 3263, 4),
(5415, 'NAICS', 219, 2371, 3, 223, 23712, 4),
(5416, 'SIC', 3124, 2400, 2, 3125, 2410, 3),
(5417, 'SIC', 4125, 7900, 2, 4131, 7930, 3),
(5418, 'SIC', 4313, 70, 1, 4081, 7500, 2),
(5419, 'SEC', 2791, 20, 1, 2461, 3713, 4),
(5420, 'NAICS', 181, 221, 2, 183, 22111, 4),
(5421, 'NAICS', 1625, 541, 2, 1631, 54119, 4),
(5422, 'SIC', 4308, 20, 1, 3258, 2990, 3),
(5423, 'NAICS', 2031, 7225, 3, 2036, 722515, 5),
(5424, 'SIC', 3409, 3490, 3, 3413, 3494, 4),
(5425, 'SEC', 2319, 2800, 2, 2331, 2850, 3),
(5426, 'NAICS', 1569, 53, 1, 1588, 53132, 4),
(5427, 'NAICS', 2103, 813, 2, 2116, 813319, 5),
(5428, 'SIC', 4308, 20, 1, 3130, 2429, 4),
(5429, 'NAICS', 1979, 713, 2, 1983, 713120, 5),
(5430, 'SIC', 3419, 3500, 2, 3427, 3531, 4),
(5431, 'SIC', 4311, 52, 1, 3811, 5260, 3),
(5432, 'SIC', 3419, 3500, 2, 3443, 3549, 4),
(5433, 'NAICS', 1726, 561, 2, 1774, 5617, 3),
(5434, 'NAICS', 999, 42384, 4, 998, 423840, 5),
(5435, 'NAICS', 1850, 62, 1, 1865, 62133, 4),
(5436, 'NAICS', 1851, 621, 2, 1879, 621493, 5),
(5437, 'SIC', 4308, 20, 1, 3234, 2844, 4),
(5438, 'NAICS', 930, 42, 1, 970, 4235, 3),
(5439, 'NAICS', 1037, 42441, 4, 1036, 424410, 5),
(5440, 'NAICS', 1598, 5322, 3, 1603, 532230, 5),
(5441, 'SIC', 4308, 20, 1, 3235, 2850, 3),
(5442, 'NAICS', 133, 211, 2, 137, 211112, 5),
(5443, 'SEC', 2403, 3500, 2, 2410, 3532, 4),
(5444, 'NAICS', 930, 42, 1, 1056, 42451, 4),
(5445, 'NAICS', 57, 1121, 3, 62, 11212, 4),
(5446, 'SIC', 3444, 3550, 3, 3445, 3552, 4),
(5447, 'NAICS', 1015, 424, 2, 1080, 42492, 4),
(5448, 'NAICS', 1419, 512, 2, 1432, 512210, 5),
(5449, 'SIC', 3715, 5000, 2, 3750, 5082, 4),
(5450, 'NAICS', 183, 22111, 4, 188, 221115, 5),
(5451, 'SIC', 4308, 20, 1, 3441, 3547, 4),
(5452, 'NAICS', 56, 112, 2, 74, 11233, 4),
(5453, 'SIC', 4097, 7540, 3, 4098, 7542, 4),
(5454, 'NAICS', 2135, 92, 1, 2182, 925, 2),
(5455, 'SEC', 2694, 6500, 2, 2695, 6510, 3),
(5456, 'NAICS', 1571, 5311, 3, 1573, 53111, 4),
(5457, 'NAICS', 1583, 5313, 3, 1587, 531320, 5),
(5458, 'SEC', 2753, 8000, 2, 2756, 8050, 3),
(5459, 'SIC', 4308, 20, 1, 3227, 2834, 4),
(5460, 'NAICS', 117, 115, 2, 122, 115113, 5),
(5461, 'SEC', 2389, 3430, 3, 2390, 3433, 4),
(5462, 'SEC', 2795, 60, 1, 2653, 6029, 4),
(5463, 'SIC', 4311, 52, 1, 3896, 5943, 4),
(5464, 'SIC', 4312, 60, 1, 3992, 6700, 2),
(5465, 'NAICS', 1990, 7139, 3, 1994, 71392, 4),
(5466, 'NAICS', 1015, 424, 2, 1064, 424690, 5),
(5467, 'NAICS', 1569, 53, 1, 1570, 531, 2),
(5468, 'NAICS', 1894, 622, 2, 1903, 62231, 4),
(5469, 'SEC', 2259, 2100, 2, 2260, 2110, 3),
(5470, 'SIC', 2825, 200, 2, 2838, 254, 4),
(5471, 'SEC', 2796, 70, 1, 2717, 7330, 3),
(5472, 'SIC', 3605, 4100, 2, 3618, 4170, 3),
(5473, 'NAICS', 1942, 71, 1, 1997, 713940, 5),
(5474, 'SIC', 4308, 20, 1, 3297, 3171, 4),
(5475, 'SIC', 3480, 3600, 2, 3492, 3633, 4),
(5476, 'SIC', 3977, 6500, 2, 3989, 6550, 3),
(5477, 'SIC', 3784, 5150, 3, 3785, 5153, 4),
(5478, 'NAICS', 930, 42, 1, 996, 423830, 5),
(5479, 'NAICS', 2053, 81121, 4, 2054, 811211, 5),
(5480, 'NAICS', 1562, 5259, 3, 1568, 52599, 4),
(5481, 'NAICS', 2177, 9241, 3, 2181, 92412, 4),
(5482, 'NAICS', 2137, 9211, 3, 2143, 92113, 4),
(5483, 'SEC', 2791, 20, 1, 2501, 3910, 3),
(5484, 'SIC', 4113, 7800, 2, 4120, 7830, 3),
(5485, 'NAICS', 930, 42, 1, 946, 4233, 3),
(5486, 'SIC', 4313, 70, 1, 4174, 8099, 4),
(5487, 'SIC', 4018, 7210, 3, 4023, 7216, 4),
(5488, 'NAICS', 1836, 6116, 3, 1838, 61161, 4),
(5489, 'SIC', 4308, 20, 1, 3289, 3143, 4),
(5490, 'SIC', 3190, 2700, 2, 3202, 2754, 4),
(5491, 'NAICS', 108, 114, 2, 109, 1141, 3),
(5492, 'NAICS', 1473, 51911, 4, 1472, 519110, 5),
(5493, 'SIC', 3555, 3820, 3, 3560, 3825, 4),
(5494, 'NAICS', 1591, 532, 2, 1616, 532420, 5),
(5495, 'NAICS', 2038, 811, 2, 2066, 81142, 4),
(5496, 'NAICS', 1726, 561, 2, 1770, 561613, 5),
(5497, 'SIC', 4040, 7300, 2, 4048, 7323, 4),
(5498, 'SIC', 4314, 90, 1, 4282, 9531, 4),
(5499, 'NAICS', 930, 42, 1, 997, 42383, 4),
(5500, 'SIC', 4312, 60, 1, 4002, 6790, 3),
(5501, 'NAICS', 1943, 711, 2, 1947, 711120, 5),
(5502, 'NAICS', 2135, 92, 1, 2154, 922120, 5),
(5503, 'SEC', 2791, 20, 1, 2272, 2320, 3),
(5504, 'SIC', 4268, 9400, 2, 4270, 9411, 4),
(5505, 'SIC', 4208, 8600, 2, 4210, 8611, 4),
(5506, 'SIC', 4308, 20, 1, 3056, 2231, 4),
(5507, 'SIC', 3311, 3250, 3, 3312, 3251, 4),
(5508, 'SEC', 2792, 40, 1, 2551, 4899, 4),
(5509, 'SEC', 2640, 5900, 2, 2648, 5990, 3),
(5510, 'SIC', 3649, 4490, 3, 3650, 4491, 4),
(5511, 'SIC', 4311, 52, 1, 3815, 5300, 2),
(5512, 'NAICS', 2137, 9211, 3, 2141, 92112, 4),
(5513, 'SEC', 2791, 20, 1, 2307, 2730, 3),
(5514, 'NAICS', 1850, 62, 1, 1917, 6239, 3),
(5515, 'NAICS', 1015, 424, 2, 1071, 4248, 3),
(5516, 'SIC', 4308, 20, 1, 3087, 2321, 4),
(5517, 'SIC', 4308, 20, 1, 3544, 3760, 3),
(5518, 'NAICS', 1996, 71393, 4, 1995, 713930, 5),
(5519, 'SEC', 2791, 20, 1, 2332, 2851, 4),
(5520, 'SIC', 3958, 6300, 2, 3961, 6320, 3),
(5521, 'SEC', 2459, 3710, 3, 2463, 3715, 4),
(5522, 'NAICS', 1073, 42481, 4, 1072, 424810, 5),
(5523, 'NAICS', 955, 4234, 3, 961, 42343, 4),
(5524, 'NAICS', 1452, 517, 2, 1458, 51721, 4),
(5525, 'NAICS', 1851, 621, 2, 1864, 621330, 5),
(5526, 'SIC', 3715, 5000, 2, 3719, 5014, 4),
(5527, 'SIC', 3480, 3600, 2, 3491, 3632, 4),
(5528, 'NAICS', 1624, 54, 1, 1701, 54186, 4),
(5529, 'SIC', 4310, 50, 1, 3792, 5171, 4),
(5530, 'NAICS', 56, 112, 2, 88, 112519, 5),
(5531, 'SIC', 4309, 40, 1, 3623, 4213, 4),
(5532, 'NAICS', 1851, 621, 2, 1863, 62132, 4),
(5533, 'NAICS', 180, 22, 1, 191, 221118, 5),
(5534, 'NAICS', 1990, 7139, 3, 1995, 713930, 5),
(5535, 'NAICS', 1667, 54151, 4, 1668, 541511, 5),
(5536, 'NAICS', 2053, 81121, 4, 2056, 811213, 5),
(5537, 'SIC', 4308, 20, 1, 3107, 2371, 4),
(5538, 'SEC', 2297, 2630, 3, 2298, 2631, 4),
(5539, 'NAICS', 1625, 541, 2, 1697, 54184, 4),
(5540, 'NAICS', 2195, 92613, 4, 2194, 926130, 5),
(5541, 'SEC', 2792, 40, 1, 2543, 4820, 3),
(5542, 'NAICS', 132, 21, 1, 179, 213115, 5),
(5543, 'NAICS', 138, 212, 2, 148, 212221, 5),
(5544, 'NAICS', 1725, 56, 1, 1801, 562212, 5),
(5545, 'NAICS', 205, 23, 1, 258, 238290, 5),
(5546, 'NAICS', 1480, 52, 1, 1524, 523210, 5),
(5547, 'SIC', 4308, 20, 1, 3202, 2754, 4),
(5548, 'SIC', 3083, 2300, 2, 3086, 2320, 3),
(5549, 'NAICS', 2135, 92, 1, 2191, 92611, 4),
(5550, 'NAICS', 2173, 92313, 4, 2172, 923130, 5),
(5551, 'SIC', 4305, 1, 1, 2854, 724, 4),
(5552, 'SIC', 4308, 20, 1, 3096, 2337, 4),
(5553, 'SIC', 3886, 5900, 2, 3898, 5945, 4),
(5554, 'SIC', 4310, 50, 1, 3749, 5080, 3),
(5555, 'SIC', 4223, 8700, 2, 4235, 8740, 3),
(5556, 'SIC', 2901, 1200, 2, 2906, 1231, 4),
(5557, 'SIC', 4306, 10, 1, 2912, 1320, 3),
(5558, 'SIC', 4308, 20, 1, 3416, 3497, 4),
(5559, 'SIC', 3225, 2830, 3, 3229, 2836, 4),
(5560, 'NAICS', 2003, 72, 1, 2006, 721110, 5),
(5561, 'NAICS', 1482, 5211, 3, 1483, 521110, 5),
(5562, 'SEC', 2738, 7800, 2, 2744, 7829, 4),
(5563, 'SIC', 4203, 8400, 2, 4207, 8422, 4),
(5564, 'SEC', 2704, 6790, 3, 2708, 6799, 4),
(5565, 'SIC', 2993, 2030, 3, 2998, 2037, 4),
(5566, 'NAICS', 1452, 517, 2, 1453, 5171, 3),
(5567, 'SIC', 3261, 3000, 2, 3273, 3081, 4),
(5568, 'NAICS', 1419, 512, 2, 1426, 512131, 5),
(5569, 'NAICS', 1928, 6242, 3, 1932, 624221, 5),
(5570, 'SEC', 2713, 7300, 2, 4329, 7385, 4),
(5571, 'SIC', 4007, 7000, 2, 4011, 7021, 4),
(5572, 'NAICS', 2103, 813, 2, 2112, 8133, 3),
(5573, 'SEC', 2479, 3820, 3, 2485, 3826, 4),
(5574, 'NAICS', 182, 2211, 3, 189, 221116, 5),
(5575, 'NAICS', 1850, 62, 1, 1929, 624210, 5),
(5576, 'NAICS', 2045, 81112, 4, 2047, 811122, 5),
(5577, 'NAICS', 1455, 51711, 4, 1454, 517110, 5),
(5578, 'SIC', 3282, 3100, 2, 3283, 3110, 3),
(5579, 'SIC', 3230, 2840, 3, 3232, 2842, 4),
(5580, 'SIC', 4307, 15, 1, 2960, 1730, 3),
(5581, 'SIC', 3419, 3500, 2, 3432, 3536, 4),
(5582, 'SEC', 2237, 1700, 2, 2239, 1731, 4),
(5583, 'SIC', 3395, 3460, 3, 3397, 3463, 4),
(5584, 'SIC', 4314, 90, 1, 4294, 9651, 4),
(5585, 'NAICS', 2, 111, 2, 37, 11141, 4),
(5586, 'SIC', 4284, 9600, 2, 4292, 9641, 4),
(5587, 'NAICS', 1, 11, 1, 123, 115114, 5),
(5588, 'SEC', 2796, 70, 1, 2783, 8744, 4),
(5589, 'SIC', 4181, 8220, 3, 4182, 8221, 4),
(5590, 'NAICS', 1015, 424, 2, 1043, 42444, 4),
(5591, 'NAICS', 2103, 813, 2, 2121, 813910, 5),
(5592, 'SIC', 4308, 20, 1, 3529, 3713, 4),
(5593, 'NAICS', 1016, 4241, 3, 1020, 42412, 4),
(5594, 'NAICS', 235, 238, 2, 244, 23814, 4),
(5595, 'NAICS', 930, 42, 1, 1042, 424440, 5),
(5596, 'SIC', 4223, 8700, 2, 4232, 8732, 4),
(5597, 'SIC', 4308, 20, 1, 3060, 2251, 4),
(5598, 'SEC', 2791, 20, 1, 2273, 2330, 3),
(5599, 'SIC', 4306, 10, 1, 2913, 1321, 4),
(5600, 'SIC', 3762, 5100, 2, 3775, 5141, 4),
(5601, 'NAICS', 2004, 721, 2, 2013, 7212, 3),
(5602, 'SIC', 3992, 6700, 2, 3997, 6722, 4),
(5603, 'NAICS', 1625, 541, 2, 1668, 541511, 5),
(5604, 'SIC', 3115, 2390, 3, 3119, 2394, 4),
(5605, 'SIC', 3423, 3520, 3, 3424, 3523, 4),
(5606, 'SIC', 4305, 1, 1, 2850, 720, 3),
(5607, 'SEC', 2795, 60, 1, 2670, 6200, 2),
(5608, 'NAICS', 1443, 5151, 3, 1447, 515120, 5),
(5609, 'NAICS', 1533, 52399, 4, 1534, 523991, 5),
(5610, 'SEC', 2791, 20, 1, 2410, 3532, 4),
(5611, 'SIC', 4309, 40, 1, 3699, 4924, 4),
(5612, 'NAICS', 1485, 522, 2, 1507, 522310, 5),
(5613, 'SEC', 2677, 6300, 2, 2687, 6360, 3),
(5614, 'SIC', 3893, 5940, 3, 3900, 5947, 4),
(5615, 'NAICS', 1449, 5152, 3, 1451, 51521, 4),
(5616, 'SIC', 4017, 7200, 2, 4025, 7218, 4),
(5617, 'NAICS', 236, 2381, 3, 250, 23817, 4),
(5618, 'SIC', 4309, 40, 1, 3615, 4142, 4),
(5619, 'NAICS', 56, 112, 2, 61, 112120, 5),
(5620, 'SEC', 2791, 20, 1, 2370, 3290, 3),
(5621, 'SIC', 2910, 1310, 3, 2911, 1311, 4),
(5622, 'SIC', 4308, 20, 1, 3481, 3610, 3),
(5623, 'NAICS', 99, 1131, 3, 101, 11311, 4),
(5624, 'SIC', 3715, 5000, 2, 3728, 5039, 4),
(5625, 'SIC', 4305, 1, 1, 2803, 116, 4),
(5626, 'NAICS', 43, 1119, 3, 51, 11194, 4),
(5627, 'NAICS', 235, 238, 2, 243, 238140, 5),
(5628, 'SIC', 4305, 1, 1, 2833, 241, 4),
(5629, 'NAICS', 1591, 532, 2, 1604, 53223, 4),
(5630, 'NAICS', 1480, 52, 1, 1531, 523930, 5),
(5631, 'SEC', 2476, 3800, 2, 2480, 3821, 4),
(5632, 'SEC', 2791, 20, 1, 2321, 2820, 3),
(5633, 'NAICS', 1624, 54, 1, 1706, 5419, 3),
(5634, 'SEC', 2796, 70, 1, 2729, 7374, 4),
(5635, 'SIC', 3131, 2430, 3, 3136, 2439, 4),
(5636, 'SIC', 4308, 20, 1, 3593, 3961, 4),
(5637, 'SIC', 3419, 3500, 2, 3479, 3599, 4),
(5638, 'NAICS', 144, 2122, 3, 155, 212299, 5),
(5639, 'SEC', 2794, 52, 1, 2628, 5660, 3),
(5640, 'SIC', 4308, 20, 1, 3123, 2399, 4),
(5641, 'SEC', 2790, 15, 1, 2235, 1620, 3),
(5642, 'SIC', 4311, 52, 1, 3831, 5450, 3),
(5643, 'SIC', 4040, 7300, 2, 4055, 7340, 3),
(5644, 'NAICS', 2107, 8132, 3, 2109, 813211, 5),
(5645, 'NAICS', 56, 112, 2, 84, 1125, 3),
(5646, 'NAICS', 229, 2373, 3, 230, 237310, 5),
(5647, 'SIC', 3419, 3500, 2, 3458, 3567, 4),
(5648, 'NAICS', 1025, 42421, 4, 1024, 424210, 5),
(5649, 'NAICS', 1625, 541, 2, 1679, 541620, 5),
(5650, 'SIC', 4309, 40, 1, 3627, 4221, 4),
(5651, 'NAICS', 1513, 523, 2, 1521, 523140, 5),
(5652, 'SIC', 3680, 4800, 2, 3687, 4832, 4),
(5653, 'SIC', 3822, 5400, 2, 3835, 5490, 3),
(5654, 'SIC', 4310, 50, 1, 3779, 5145, 4),
(5655, 'SIC', 3978, 6510, 3, 3983, 6517, 4),
(5656, 'SIC', 2955, 1700, 2, 2959, 1721, 4),
(5657, 'SIC', 4307, 15, 1, 2970, 1761, 4),
(5658, 'NAICS', 1689, 5418, 3, 1697, 54184, 4),
(5659, 'SIC', 4308, 20, 1, 3394, 3452, 4),
(5660, 'NAICS', 1850, 62, 1, 1903, 62231, 4),
(5661, 'SIC', 4308, 20, 1, 3236, 2851, 4),
(5662, 'NAICS', 118, 1151, 3, 122, 115113, 5),
(5663, 'NAICS', 260, 2383, 3, 271, 238390, 5),
(5664, 'NAICS', 1591, 532, 2, 1619, 53249, 4),
(5665, 'NAICS', 1792, 562, 2, 1796, 562112, 5),
(5666, 'SIC', 3605, 4100, 2, 3613, 4140, 3),
(5667, 'NAICS', 1885, 6216, 3, 1886, 621610, 5),
(5668, 'SIC', 3174, 2650, 3, 3178, 2656, 4),
(5669, 'NAICS', 1652, 54136, 4, 1651, 541360, 5),
(5670, 'SIC', 4312, 60, 1, 3996, 6720, 3),
(5671, 'NAICS', 1847, 6117, 3, 1849, 61171, 4),
(5672, 'NAICS', 2135, 92, 1, 2153, 92211, 4),
(5673, 'SIC', 2955, 1700, 2, 2966, 1750, 3),
(5674, 'NAICS', 932, 4231, 3, 939, 423140, 5),
(5675, 'NAICS', 1402, 51, 1, 1463, 51791, 4),
(5676, 'NAICS', 219, 2371, 3, 224, 237130, 5),
(5677, 'SIC', 3371, 3400, 2, 3399, 3466, 4),
(5678, 'SIC', 4313, 70, 1, 4155, 8042, 4),
(5679, 'SIC', 2918, 1400, 2, 2926, 1442, 4),
(5680, 'SIC', 3041, 2100, 2, 3046, 2130, 3),
(5681, 'SEC', 2649, 6000, 2, 2657, 6090, 3),
(5682, 'SIC', 3083, 2300, 2, 3115, 2390, 3),
(5683, 'SEC', 2384, 3400, 2, 2390, 3433, 4),
(5684, 'SIC', 4308, 20, 1, 3338, 3310, 3),
(5685, 'SIC', 3693, 4900, 2, 3705, 4940, 3),
(5686, 'SEC', 2545, 4830, 3, 2547, 4833, 4),
(5687, 'SIC', 4308, 20, 1, 3269, 3060, 3),
(5688, 'SIC', 3756, 5090, 3, 3759, 5093, 4),
(5689, 'SIC', 4308, 20, 1, 3005, 2046, 4),
(5690, 'NAICS', 1625, 541, 2, 1636, 541211, 5),
(5691, 'SEC', 2791, 20, 1, 2393, 3443, 4),
(5692, 'SIC', 4307, 15, 1, 2965, 1743, 4),
(5693, 'SIC', 2948, 1600, 2, 2953, 1623, 4),
(5694, 'SIC', 3886, 5900, 2, 3916, 5999, 4),
(5695, 'SEC', 2713, 7300, 2, 2726, 7371, 4),
(5696, 'NAICS', 2, 111, 2, 17, 111191, 5),
(5697, 'SEC', 2677, 6300, 2, 2686, 6351, 4),
(5698, 'SEC', 2795, 60, 1, 2681, 6321, 4),
(5699, 'SIC', 4305, 1, 1, 2825, 200, 2),
(5700, 'NAICS', 2120, 8139, 3, 2125, 813930, 5),
(5701, 'NAICS', 1754, 56149, 4, 1757, 561499, 5),
(5702, 'NAICS', 2004, 721, 2, 2010, 72119, 4),
(5703, 'SIC', 4308, 20, 1, 3158, 2522, 4),
(5704, 'SIC', 4313, 70, 1, 4020, 7212, 4),
(5705, 'NAICS', 1480, 52, 1, 1532, 52393, 4),
(5706, 'SEC', 2292, 2600, 2, 2296, 2621, 4),
(5707, 'NAICS', 277, 23899, 4, 276, 238990, 5),
(5708, 'SIC', 3148, 2500, 2, 3157, 2521, 4),
(5709, 'SIC', 4310, 50, 1, 3730, 5043, 4),
(5710, 'NAICS', 1804, 5629, 3, 1809, 56299, 4),
(5711, 'SIC', 4314, 90, 1, 4261, 9222, 4),
(5712, 'SIC', 3261, 3000, 2, 3277, 3085, 4),
(5713, 'NAICS', 1591, 532, 2, 1608, 532299, 5),
(5714, 'SIC', 4308, 20, 1, 3220, 2820, 3),
(5715, 'NAICS', 2183, 9251, 3, 2187, 92512, 4),
(5716, 'NAICS', 1419, 512, 2, 1438, 512240, 5),
(5717, 'NAICS', 57, 1121, 3, 60, 112112, 5),
(5718, 'NAICS', 2066, 81142, 4, 2065, 811420, 5),
(5719, 'NAICS', 2188, 926, 2, 2190, 926110, 5),
(5720, 'NAICS', 2039, 8111, 3, 2048, 81119, 4),
(5721, 'SIC', 3662, 4600, 2, 3664, 4612, 4),
(5722, 'SEC', 2221, 1300, 2, 2227, 1389, 4),
(5723, 'NAICS', 2137, 9211, 3, 2142, 921130, 5),
(5724, 'NAICS', 2135, 92, 1, 2140, 921120, 5),
(5725, 'NAICS', 1725, 56, 1, 1765, 561599, 5),
(5726, 'SIC', 3917, 6000, 2, 3929, 6061, 4),
(5727, 'SIC', 3496, 3640, 3, 3501, 3646, 4),
(5728, 'NAICS', 1625, 541, 2, 1641, 541310, 5),
(5729, 'SEC', 2791, 20, 1, 2434, 3600, 2),
(5730, 'NAICS', 23, 1113, 3, 33, 111335, 5),
(5731, 'NAICS', 1994, 71392, 4, 1993, 713920, 5),
(5732, 'NAICS', 144, 2122, 3, 154, 212291, 5),
(5733, 'NAICS', 183, 22111, 4, 185, 221112, 5),
(5734, 'NAICS', 1536, 524, 2, 1539, 524113, 5),
(5735, 'NAICS', 1625, 541, 2, 1682, 54169, 4),
(5736, 'SIC', 4266, 9310, 3, 4267, 9311, 4),
(5737, 'SIC', 2969, 1760, 3, 2970, 1761, 4),
(5738, 'NAICS', 1004, 4239, 3, 1013, 423990, 5),
(5739, 'NAICS', 1727, 5611, 3, 1728, 561110, 5),
(5740, 'SIC', 3489, 3630, 3, 3491, 3632, 4),
(5741, 'SIC', 3822, 5400, 2, 3825, 5420, 3),
(5742, 'SIC', 4017, 7200, 2, 4039, 7299, 4),
(5743, 'NAICS', 1015, 424, 2, 1019, 424120, 5),
(5744, 'NAICS', 1015, 424, 2, 1033, 424340, 5),
(5745, 'SEC', 2479, 3820, 3, 2480, 3821, 4),
(5746, 'NAICS', 3, 1111, 3, 8, 111130, 5),
(5747, 'SIC', 3195, 2730, 3, 3196, 2731, 4),
(5748, 'NAICS', 1792, 562, 2, 1797, 562119, 5),
(5749, 'SEC', 2694, 6500, 2, 2698, 6519, 4),
(5750, 'NAICS', 2104, 8131, 3, 2105, 813110, 5),
(5751, 'NAICS', 117, 115, 2, 121, 115112, 5),
(5752, 'NAICS', 1793, 5621, 3, 1795, 562111, 5),
(5753, 'NAICS', 1624, 54, 1, 1702, 541870, 5),
(5754, 'NAICS', 181, 221, 2, 199, 221310, 5),
(5755, 'NAICS', 1416, 5112, 3, 1418, 51121, 4),
(5756, 'NAICS', 1525, 52321, 4, 1524, 523210, 5),
(5757, 'SEC', 2713, 7300, 2, 2716, 7320, 3),
(5758, 'SEC', 2796, 70, 1, 2741, 7819, 4),
(5759, 'SIC', 3715, 5000, 2, 3745, 5072, 4),
(5760, 'SIC', 4312, 60, 1, 3941, 6141, 4),
(5761, 'SIC', 4313, 70, 1, 4008, 7010, 3),
(5762, 'NAICS', 1, 11, 1, 78, 11239, 4),
(5763, 'SEC', 2791, 20, 1, 2473, 3751, 4),
(5764, 'SIC', 3815, 5300, 2, 3816, 5310, 3),
(5765, 'SIC', 4313, 70, 1, 4212, 8621, 4),
(5766, 'NAICS', 967, 42346, 4, 966, 423460, 5),
(5767, 'SIC', 4308, 20, 1, 3536, 3728, 4),
(5768, 'NAICS', 1625, 541, 2, 1714, 541940, 5),
(5769, 'SIC', 3937, 6100, 2, 3945, 6160, 3),
(5770, 'SIC', 4208, 8600, 2, 4213, 8630, 3),
(5771, 'NAICS', 1026, 4243, 3, 1032, 42433, 4),
(5772, 'SIC', 3337, 3300, 2, 3361, 3357, 4),
(5773, 'NAICS', 2, 111, 2, 27, 11132, 4),
(5774, 'NAICS', 2150, 922, 2, 2157, 92213, 4),
(5775, 'SEC', 2476, 3800, 2, 2485, 3826, 4),
(5776, 'NAICS', 2151, 9221, 3, 2158, 922140, 5),
(5777, 'SEC', 2342, 3000, 2, 2347, 3050, 3),
(5778, 'SEC', 2791, 20, 1, 2345, 3020, 3),
(5779, 'NAICS', 235, 238, 2, 268, 23834, 4),
(5780, 'SIC', 3330, 3290, 3, 3334, 3296, 4),
(5781, 'NAICS', 1725, 56, 1, 1737, 561320, 5),
(5782, 'NAICS', 1920, 624, 2, 1925, 62412, 4),
(5783, 'SEC', 2791, 20, 1, 2400, 3470, 3),
(5784, 'SEC', 2552, 4900, 2, 2558, 4924, 4),
(5785, 'NAICS', 930, 42, 1, 1062, 424610, 5),
(5786, 'NAICS', 1709, 54192, 4, 1711, 541922, 5),
(5787, 'SEC', 2792, 40, 1, 2541, 4812, 4),
(5788, 'SEC', 2775, 8710, 3, 2776, 8711, 4),
(5789, 'NAICS', 1089, 425, 2, 1093, 425120, 5),
(5790, 'SIC', 4309, 40, 1, 3664, 4612, 4),
(5791, 'NAICS', 221, 23711, 4, 220, 237110, 5),
(5792, 'SIC', 3681, 4810, 3, 3683, 4813, 4),
(5793, 'SEC', 2790, 15, 1, 2239, 1731, 4),
(5794, 'SIC', 3272, 3080, 3, 3277, 3085, 4),
(5795, 'NAICS', 1850, 62, 1, 1871, 6214, 3),
(5796, 'NAICS', 1851, 621, 2, 1893, 621999, 5),
(5797, 'SIC', 4313, 70, 1, 4184, 8230, 3),
(5798, 'SEC', 2262, 2200, 2, 2264, 2211, 4),
(5799, 'SIC', 4313, 70, 1, 4123, 7840, 3),
(5800, 'NAICS', 2004, 721, 2, 2014, 72121, 4),
(5801, 'SIC', 3542, 3750, 3, 3543, 3751, 4),
(5802, 'NAICS', 1452, 517, 2, 1457, 517210, 5),
(5803, 'NAICS', 1850, 62, 1, 1889, 621910, 5),
(5804, 'NAICS', 1625, 541, 2, 1711, 541922, 5),
(5805, 'SEC', 2792, 40, 1, 2539, 4800, 2),
(5806, 'NAICS', 1006, 42391, 4, 1005, 423910, 5),
(5807, 'NAICS', 1624, 54, 1, 1681, 541690, 5),
(5808, 'SIC', 2798, 100, 2, 2822, 182, 4),
(5809, 'SIC', 4307, 15, 1, 2940, 1520, 3),
(5810, 'NAICS', 2, 111, 2, 21, 111211, 5),
(5811, 'SIC', 2987, 2020, 3, 2988, 2021, 4),
(5812, 'SIC', 3701, 4930, 3, 3704, 4939, 4),
(5813, 'SEC', 2795, 60, 1, 2706, 6794, 4),
(5814, 'SEC', 2796, 70, 1, 2709, 7000, 2),
(5815, 'NAICS', 2061, 8114, 3, 2070, 81149, 4),
(5816, 'NAICS', 1068, 42471, 4, 1067, 424710, 5),
(5817, 'NAICS', 1625, 541, 2, 1667, 54151, 4),
(5818, 'SEC', 2777, 8730, 3, 2778, 8731, 4),
(5819, 'SEC', 2505, 3940, 3, 2506, 3942, 4),
(5820, 'SEC', 2240, 2000, 2, 2246, 2024, 4),
(5821, 'SIC', 4313, 70, 1, 4166, 8070, 3),
(5822, 'SIC', 2955, 1700, 2, 2972, 1771, 4),
(5823, 'NAICS', 2003, 72, 1, 2025, 72232, 4),
(5824, 'SIC', 3996, 6720, 3, 3997, 6722, 4),
(5825, 'NAICS', 2136, 921, 2, 2146, 921150, 5),
(5826, 'SIC', 4012, 7030, 3, 4014, 7033, 4),
(5827, 'NAICS', 1812, 61, 1, 1822, 61131, 4),
(5828, 'NAICS', 2004, 721, 2, 2008, 721120, 5),
(5829, 'SEC', 2791, 20, 1, 2490, 3842, 4),
(5830, 'SEC', 2600, 5170, 3, 2601, 5171, 4),
(5831, 'NAICS', 3, 1111, 3, 16, 11119, 4),
(5832, 'NAICS', 1015, 424, 2, 1031, 424330, 5),
(5833, 'SIC', 4040, 7300, 2, 4056, 7342, 4),
(5834, 'NAICS', 1402, 51, 1, 1447, 515120, 5),
(5835, 'NAICS', 1718, 55, 1, 1719, 551, 2),
(5836, 'NAICS', 2020, 722, 2, 2034, 722513, 5),
(5837, 'SIC', 4308, 20, 1, 3470, 3582, 4),
(5838, 'SIC', 4186, 8240, 3, 4187, 8243, 4),
(5839, 'NAICS', 1480, 52, 1, 1498, 522220, 5),
(5840, 'NAICS', 1, 11, 1, 19, 1112, 3),
(5841, 'SIC', 4312, 60, 1, 3975, 6410, 3),
(5842, 'NAICS', 1943, 711, 2, 1957, 711219, 5),
(5843, 'NAICS', 1, 11, 1, 10, 111140, 5),
(5844, 'NAICS', 981, 42369, 4, 980, 423690, 5),
(5845, 'SIC', 3235, 2850, 3, 3236, 2851, 4),
(5846, 'NAICS', 1689, 5418, 3, 1693, 54182, 4),
(5847, 'NAICS', 1625, 541, 2, 1716, 541990, 5),
(5848, 'SIC', 3489, 3630, 3, 3492, 3633, 4),
(5849, 'SIC', 4223, 8700, 2, 4240, 8748, 4),
(5850, 'NAICS', 1419, 512, 2, 1436, 512230, 5),
(5851, 'SIC', 4306, 10, 1, 2888, 1021, 4),
(5852, 'SEC', 2748, 7900, 2, 2750, 7948, 4),
(5853, 'SIC', 2884, 1000, 2, 2900, 1099, 4),
(5854, 'NAICS', 1624, 54, 1, 1640, 5413, 3),
(5855, 'SEC', 2218, 1200, 2, 2220, 1221, 4),
(5856, 'SIC', 2940, 1520, 3, 2942, 1522, 4),
(5857, 'NAICS', 1625, 541, 2, 1709, 54192, 4),
(5858, 'NAICS', 1979, 713, 2, 1991, 713910, 5),
(5859, 'SIC', 4309, 40, 1, 3698, 4923, 4),
(5860, 'SIC', 3749, 5080, 3, 3750, 5082, 4),
(5861, 'SIC', 3620, 4200, 2, 3632, 4231, 4),
(5862, 'NAICS', 2177, 9241, 3, 2180, 924120, 5),
(5863, 'NAICS', 1850, 62, 1, 1858, 62121, 4),
(5864, 'NAICS', 2189, 9261, 3, 2196, 926140, 5),
(5865, 'SIC', 3667, 4700, 2, 3673, 4731, 4),
(5866, 'SEC', 2791, 20, 1, 2335, 2890, 3),
(5867, 'SIC', 4308, 20, 1, 3247, 2891, 4),
(5868, 'NAICS', 2, 111, 2, 20, 11121, 4),
(5869, 'NAICS', 1624, 54, 1, 1712, 541930, 5),
(5870, 'SEC', 2315, 2770, 3, 2316, 2771, 4),
(5871, 'NAICS', 126, 1152, 3, 127, 115210, 5),
(5872, 'NAICS', 930, 42, 1, 1003, 42386, 4),
(5873, 'NAICS', 2037, 81, 1, 2070, 81149, 4),
(5874, 'SEC', 2355, 3200, 2, 2363, 3241, 4),
(5875, 'SEC', 2678, 6310, 3, 2679, 6311, 4),
(5876, 'SIC', 4306, 10, 1, 2898, 1090, 3),
(5877, 'NAICS', 272, 23839, 4, 271, 238390, 5),
(5878, 'NAICS', 1979, 713, 2, 1988, 713290, 5),
(5879, 'NAICS', 1513, 523, 2, 1535, 523999, 5),
(5880, 'SIC', 2955, 1700, 2, 2980, 1796, 4),
(5881, 'NAICS', 1402, 51, 1, 1473, 51911, 4),
(5882, 'SIC', 2825, 200, 2, 2830, 214, 4),
(5883, 'NAICS', 950, 42332, 4, 949, 423320, 5),
(5884, 'NAICS', 1592, 5321, 3, 1594, 532111, 5),
(5885, 'NAICS', 1851, 621, 2, 1875, 62142, 4),
(5886, 'SEC', 2791, 20, 1, 2289, 2531, 4),
(5887, 'NAICS', 954, 42339, 4, 953, 423390, 5),
(5888, 'NAICS', 1609, 5323, 3, 1610, 532310, 5),
(5889, 'SEC', 2694, 6500, 2, 2700, 6531, 4),
(5890, 'NAICS', 205, 23, 1, 265, 238330, 5),
(5891, 'SEC', 2796, 70, 1, 2746, 7840, 3),
(5892, 'NAICS', 1480, 52, 1, 1561, 52519, 4),
(5893, 'SIC', 3041, 2100, 2, 3044, 2120, 3),
(5894, 'SIC', 2901, 1200, 2, 2903, 1221, 4),
(5895, 'SIC', 4308, 20, 1, 3088, 2322, 4),
(5896, 'SIC', 3461, 3570, 3, 3464, 3575, 4),
(5897, 'SIC', 4308, 20, 1, 3116, 2391, 4),
(5898, 'SIC', 3180, 2670, 3, 3185, 2675, 4),
(5899, 'NAICS', 1402, 51, 1, 1425, 51213, 4),
(5900, 'SIC', 4313, 70, 1, 4096, 7539, 4),
(5901, 'SEC', 2791, 20, 1, 2378, 3340, 3),
(5902, 'NAICS', 1076, 4249, 3, 1085, 424950, 5),
(5903, 'NAICS', 1943, 711, 2, 1960, 71131, 4),
(5904, 'SIC', 4308, 20, 1, 3363, 3363, 4),
(5905, 'NAICS', 9, 11113, 4, 8, 111130, 5),
(5906, 'NAICS', 235, 238, 2, 238, 23811, 4),
(5907, 'SIC', 3668, 4720, 3, 3669, 4724, 4),
(5908, 'NAICS', 162, 21232, 4, 164, 212322, 5),
(5909, 'SEC', 2610, 5300, 2, 2616, 5399, 4),
(5910, 'SEC', 2796, 70, 1, 2761, 8071, 4),
(5911, 'SIC', 4308, 20, 1, 3579, 3914, 4),
(5912, 'NAICS', 207, 2361, 3, 210, 236116, 5),
(5913, 'NAICS', 2020, 722, 2, 2035, 722514, 5),
(5914, 'NAICS', 138, 212, 2, 141, 212111, 5),
(5915, 'SIC', 4313, 70, 1, 4064, 7363, 4),
(5916, 'NAICS', 1444, 51511, 4, 1445, 515111, 5),
(5917, 'SIC', 3057, 2240, 3, 3058, 2241, 4),
(5918, 'SIC', 3322, 3270, 3, 3326, 3274, 4),
(5919, 'NAICS', 930, 42, 1, 1011, 423940, 5),
(5920, 'NAICS', 930, 42, 1, 994, 423820, 5),
(5921, 'SIC', 2901, 1200, 2, 2908, 1241, 4),
(5922, 'SIC', 3214, 2800, 2, 3250, 2895, 4),
(5923, 'SIC', 4306, 10, 1, 2919, 1410, 3),
(5924, 'SIC', 4309, 40, 1, 3642, 4432, 4),
(5925, 'NAICS', 1419, 512, 2, 1421, 512110, 5),
(5926, 'NAICS', 1850, 62, 1, 1914, 62331, 4),
(5927, 'NAICS', 2038, 811, 2, 2044, 811118, 5),
(5928, 'SIC', 4310, 50, 1, 3771, 5136, 4),
(5929, 'NAICS', 1979, 713, 2, 2001, 713990, 5),
(5930, 'NAICS', 1876, 62149, 4, 1880, 621498, 5),
(5931, 'SEC', 2713, 7300, 2, 2734, 7389, 4),
(5932, 'SIC', 3480, 3600, 2, 3510, 3669, 4),
(5933, 'NAICS', 930, 42, 1, 1007, 423920, 5),
(5934, 'NAICS', 1485, 522, 2, 1510, 52232, 4),
(5935, 'NAICS', 1562, 5259, 3, 1565, 525920, 5),
(5936, 'SIC', 4256, 9200, 2, 4259, 9220, 3),
(5937, 'NAICS', 1537, 5241, 3, 1544, 524128, 5),
(5938, 'NAICS', 1, 11, 1, 33, 111335, 5),
(5939, 'SEC', 2355, 3200, 2, 2360, 3230, 3),
(5940, 'SEC', 2456, 3690, 3, 2457, 3695, 4),
(5941, 'SIC', 4313, 70, 1, 4013, 7032, 4),
(5942, 'NAICS', 1730, 5612, 3, 1732, 56121, 4),
(5943, 'NAICS', 1605, 53229, 4, 1606, 532291, 5),
(5944, 'SIC', 4308, 20, 1, 3465, 3577, 4),
(5945, 'NAICS', 1725, 56, 1, 1751, 56144, 4),
(5946, 'SIC', 3272, 3080, 3, 3273, 3081, 4),
(5947, 'SIC', 3721, 5020, 3, 3723, 5023, 4),
(5948, 'SEC', 2792, 40, 1, 2537, 4730, 3),
(5949, 'NAICS', 1901, 6223, 3, 1902, 622310, 5),
(5950, 'SIC', 3214, 2800, 2, 3222, 2822, 4),
(5951, 'SEC', 2319, 2800, 2, 2327, 2836, 4),
(5952, 'SIC', 4313, 70, 1, 4170, 8082, 4),
(5953, 'SIC', 3261, 3000, 2, 3272, 3080, 3),
(5954, 'SIC', 3859, 5630, 3, 3860, 5632, 4),
(5955, 'NAICS', 955, 4234, 3, 964, 423450, 5),
(5956, 'SIC', 4313, 70, 1, 4019, 7211, 4),
(5957, 'SIC', 2982, 2000, 2, 3038, 2097, 4),
(5958, 'NAICS', 1557, 52511, 4, 1556, 525110, 5),
(5959, 'NAICS', 931, 423, 2, 941, 4232, 3),
(5960, 'NAICS', 1726, 561, 2, 1752, 561450, 5),
(5961, 'SEC', 2793, 50, 1, 2573, 5031, 4),
(5962, 'SIC', 3605, 4100, 2, 3617, 4151, 4),
(5963, 'NAICS', 1625, 541, 2, 1693, 54182, 4),
(5964, 'NAICS', 1831, 61151, 4, 1834, 611513, 5),
(5965, 'SEC', 2791, 20, 1, 2350, 3081, 4),
(5966, 'SIC', 3285, 3130, 3, 3286, 3131, 4),
(5967, 'NAICS', 1850, 62, 1, 1874, 621420, 5),
(5968, 'SIC', 3958, 6300, 2, 3971, 6371, 4),
(5969, 'NAICS', 1569, 53, 1, 1574, 531120, 5),
(5970, 'NAICS', 218, 237, 2, 220, 237110, 5),
(5971, 'NAICS', 1480, 52, 1, 1516, 52311, 4),
(5972, 'SEC', 2791, 20, 1, 2374, 3317, 4),
(5973, 'SIC', 3886, 5900, 2, 3897, 5944, 4),
(5974, 'SIC', 4313, 70, 1, 4082, 7510, 3),
(5975, 'NAICS', 1813, 611, 2, 1840, 61162, 4),
(5976, 'NAICS', 1442, 515, 2, 1446, 515112, 5),
(5977, 'NAICS', 1569, 53, 1, 1591, 532, 2),
(5978, 'NAICS', 1495, 5222, 3, 1496, 522210, 5),
(5979, 'SIC', 3124, 2400, 2, 3133, 2434, 4),
(5980, 'NAICS', 930, 42, 1, 966, 423460, 5),
(5981, 'SIC', 4308, 20, 1, 3104, 2361, 4),
(5982, 'SIC', 4309, 40, 1, 3654, 4500, 2),
(5983, 'NAICS', 1480, 52, 1, 1484, 52111, 4),
(5984, 'SIC', 2951, 1620, 3, 2952, 1622, 4),
(5985, 'SIC', 4311, 52, 1, 3806, 5211, 4),
(5986, 'SIC', 4313, 70, 1, 4180, 8211, 4),
(5987, 'NAICS', 206, 236, 2, 210, 236116, 5),
(5988, 'NAICS', 1726, 561, 2, 1731, 561210, 5),
(5989, 'SIC', 4257, 9210, 3, 4258, 9211, 4),
(5990, 'NAICS', 1850, 62, 1, 1927, 62419, 4),
(5991, 'NAICS', 2104, 8131, 3, 2106, 81311, 4),
(5992, 'NAICS', 1480, 52, 1, 1556, 525110, 5),
(5993, 'SEC', 2477, 3810, 3, 2478, 3812, 4),
(5994, 'NAICS', 1480, 52, 1, 1499, 52222, 4),
(5995, 'SIC', 2982, 2000, 2, 3009, 2051, 4),
(5996, 'NAICS', 118, 1151, 3, 121, 115112, 5),
(5997, 'SIC', 3261, 3000, 2, 3270, 3061, 4),
(5998, 'NAICS', 1480, 52, 1, 1537, 5241, 3),
(5999, 'NAICS', 1925, 62412, 4, 1924, 624120, 5),
(6000, 'SIC', 4308, 20, 1, 3010, 2052, 4),
(6001, 'SEC', 2328, 2840, 3, 2329, 2842, 4),
(6002, 'SIC', 3086, 2320, 3, 3090, 2325, 4),
(6003, 'NAICS', 1569, 53, 1, 1594, 532111, 5),
(6004, 'NAICS', 1727, 5611, 3, 1729, 56111, 4),
(6005, 'SIC', 4284, 9600, 2, 4291, 9640, 3),
(6006, 'NAICS', 1, 11, 1, 107, 11331, 4),
(6007, 'NAICS', 1419, 512, 2, 1434, 512220, 5),
(6008, 'NAICS', 1495, 5222, 3, 1502, 522292, 5),
(6009, 'SIC', 2825, 200, 2, 2843, 273, 4),
(6010, 'SIC', 4308, 20, 1, 3395, 3460, 3),
(6011, 'SIC', 4017, 7200, 2, 4021, 7213, 4),
(6012, 'SIC', 4310, 50, 1, 3732, 5045, 4),
(6013, 'SEC', 2792, 40, 1, 2524, 4410, 3),
(6014, 'SIC', 3643, 4440, 3, 3644, 4449, 4),
(6015, 'NAICS', 257, 23822, 4, 256, 238220, 5),
(6016, 'SIC', 4312, 60, 1, 3958, 6300, 2),
(6017, 'SIC', 4166, 8070, 3, 4168, 8072, 4),
(6018, 'SEC', 2796, 70, 1, 2768, 8111, 4),
(6019, 'SEC', 2738, 7800, 2, 2742, 7820, 3),
(6020, 'SEC', 2791, 20, 1, 2402, 3490, 3),
(6021, 'NAICS', 1928, 6242, 3, 1931, 62422, 4),
(6022, 'NAICS', 1035, 4244, 3, 1048, 424470, 5),
(6023, 'SEC', 2600, 5170, 3, 2602, 5172, 4),
(6024, 'SEC', 2240, 2000, 2, 2245, 2020, 3),
(6025, 'SIC', 4082, 7510, 3, 4084, 7514, 4),
(6026, 'SEC', 2794, 52, 1, 2617, 5400, 2),
(6027, 'SIC', 3889, 5920, 3, 3890, 5921, 4),
(6028, 'NAICS', 192, 22112, 4, 194, 221122, 5),
(6029, 'NAICS', 1, 11, 1, 13, 11115, 4),
(6030, 'SIC', 4308, 20, 1, 3387, 3443, 4),
(6031, 'SIC', 3261, 3000, 2, 3262, 3010, 3),
(6032, 'NAICS', 1, 11, 1, 91, 11291, 4),
(6033, 'SIC', 4314, 90, 1, 4257, 9210, 3),
(6034, 'SIC', 4308, 20, 1, 3459, 3568, 4),
(6035, 'SIC', 4309, 40, 1, 3677, 4783, 4),
(6036, 'NAICS', 1569, 53, 1, 1572, 531110, 5),
(6037, 'SIC', 4308, 20, 1, 3032, 2087, 4),
(6038, 'NAICS', 2145, 92114, 4, 2144, 921140, 5),
(6039, 'NAICS', 235, 238, 2, 255, 23821, 4),
(6040, 'SEC', 2791, 20, 1, 2385, 3410, 3),
(6041, 'SIC', 4208, 8600, 2, 4214, 8631, 4),
(6042, 'SIC', 4308, 20, 1, 3562, 3827, 4),
(6043, 'NAICS', 262, 23831, 4, 261, 238310, 5),
(6044, 'SIC', 4208, 8600, 2, 4209, 8610, 3),
(6045, 'SEC', 2792, 40, 1, 2516, 4100, 2),
(6046, 'SIC', 4308, 20, 1, 3515, 3675, 4),
(6047, 'NAICS', 1402, 51, 1, 1420, 5121, 3),
(6048, 'NAICS', 1634, 5412, 3, 1638, 541214, 5),
(6049, 'NAICS', 1920, 624, 2, 1921, 6241, 3),
(6050, 'SIC', 3282, 3100, 2, 3297, 3171, 4),
(6051, 'SIC', 3784, 5150, 3, 3786, 5154, 4),
(6052, 'NAICS', 1903, 62231, 4, 1902, 622310, 5),
(6053, 'NAICS', 1942, 71, 1, 1984, 71312, 4),
(6054, 'SEC', 2694, 6500, 2, 2699, 6530, 3),
(6055, 'SIC', 3053, 2220, 3, 3054, 2221, 4),
(6056, 'NAICS', 930, 42, 1, 969, 42349, 4),
(6057, 'NAICS', 1066, 4247, 3, 1067, 424710, 5),
(6058, 'SIC', 4309, 40, 1, 3643, 4440, 3),
(6059, 'SEC', 2310, 2740, 3, 2311, 2741, 4),
(6060, 'SEC', 2596, 5140, 3, 2597, 5141, 4),
(6061, 'NAICS', 198, 2213, 3, 199, 221310, 5),
(6062, 'SEC', 2610, 5300, 2, 2615, 5390, 3),
(6063, 'SIC', 4308, 20, 1, 3274, 3082, 4),
(6064, 'SIC', 3282, 3100, 2, 3289, 3143, 4),
(6065, 'SIC', 3371, 3400, 2, 3397, 3463, 4),
(6066, 'NAICS', 1851, 621, 2, 1892, 621991, 5),
(6067, 'SIC', 4308, 20, 1, 3125, 2410, 3),
(6068, 'NAICS', 2037, 81, 1, 2087, 81231, 4),
(6069, 'NAICS', 2061, 8114, 3, 2066, 81142, 4),
(6070, 'SIC', 2982, 2000, 2, 3014, 2062, 4),
(6071, 'SIC', 2982, 2000, 2, 3004, 2045, 4),
(6072, 'SEC', 2720, 7350, 3, 2721, 7359, 4),
(6073, 'NAICS', 1726, 561, 2, 1763, 56159, 4),
(6074, 'SIC', 3715, 5000, 2, 3737, 5050, 3),
(6075, 'SIC', 3992, 6700, 2, 3995, 6719, 4),
(6076, 'SIC', 4313, 70, 1, 4131, 7930, 3),
(6077, 'SIC', 3124, 2400, 2, 3130, 2429, 4),
(6078, 'SIC', 2982, 2000, 2, 3024, 2077, 4),
(6079, 'SIC', 4308, 20, 1, 3534, 3721, 4),
(6080, 'SIC', 4308, 20, 1, 3600, 3999, 4),
(6081, 'NAICS', 132, 21, 1, 148, 212221, 5),
(6082, 'NAICS', 1905, 6231, 3, 1906, 623110, 5),
(6083, 'SEC', 2222, 1310, 3, 2223, 1311, 4),
(6084, 'SIC', 3026, 2080, 3, 3032, 2087, 4),
(6085, 'NAICS', 931, 423, 2, 977, 42361, 4),
(6086, 'NAICS', 2135, 92, 1, 2208, 928120, 5),
(6087, 'SIC', 3820, 5390, 3, 3821, 5399, 4),
(6088, 'SIC', 2982, 2000, 2, 3008, 2050, 3),
(6089, 'SIC', 4146, 8000, 2, 4168, 8072, 4),
(6090, 'SIC', 4305, 1, 1, 2861, 760, 3),
(6091, 'NAICS', 68, 1123, 3, 75, 112340, 5),
(6092, 'SIC', 4308, 20, 1, 3021, 2074, 4),
(6093, 'NAICS', 930, 42, 1, 1089, 425, 2),
(6094, 'NAICS', 2071, 812, 2, 2096, 81292, 4),
(6095, 'NAICS', 1689, 5418, 3, 1703, 54187, 4),
(6096, 'NAICS', 931, 423, 2, 952, 42333, 4),
(6097, 'SIC', 4308, 20, 1, 3590, 3953, 4),
(6098, 'SIC', 4305, 1, 1, 2852, 722, 4),
(6099, 'SIC', 3148, 2500, 2, 3155, 2519, 4),
(6100, 'SIC', 4310, 50, 1, 3760, 5094, 4),
(6101, 'SEC', 2488, 3840, 3, 2489, 3841, 4),
(6102, 'SEC', 2434, 3600, 2, 2450, 3670, 3),
(6103, 'SIC', 4306, 10, 1, 2909, 1300, 2),
(6104, 'NAICS', 1480, 52, 1, 1530, 52392, 4),
(6105, 'NAICS', 1506, 5223, 3, 1511, 522390, 5),
(6106, 'NAICS', 1836, 6116, 3, 1842, 61163, 4),
(6107, 'NAICS', 2048, 81119, 4, 2051, 811198, 5),
(6108, 'SEC', 2292, 2600, 2, 2297, 2630, 3),
(6109, 'SIC', 4311, 52, 1, 3902, 5949, 4),
(6110, 'NAICS', 930, 42, 1, 976, 423610, 5),
(6111, 'SIC', 4313, 70, 1, 4053, 7336, 4),
(6112, 'NAICS', 2060, 81131, 4, 2059, 811310, 5),
(6113, 'NAICS', 1625, 541, 2, 1666, 5415, 3),
(6114, 'SIC', 4308, 20, 1, 3457, 3566, 4),
(6115, 'NAICS', 930, 42, 1, 1043, 42444, 4),
(6116, 'NAICS', 1, 11, 1, 82, 112420, 5),
(6117, 'SEC', 2793, 50, 1, 2574, 5040, 3),
(6118, 'SIC', 3395, 3460, 3, 3399, 3466, 4),
(6119, 'SIC', 4308, 20, 1, 3368, 3390, 3),
(6120, 'NAICS', 2093, 8129, 3, 2100, 81293, 4),
(6121, 'NAICS', 2193, 92612, 4, 2192, 926120, 5),
(6122, 'NAICS', 931, 423, 2, 942, 423210, 5),
(6123, 'NAICS', 1569, 53, 1, 1603, 532230, 5),
(6124, 'SEC', 2792, 40, 1, 2517, 4200, 2),
(6125, 'NAICS', 1625, 541, 2, 1696, 541840, 5),
(6126, 'SIC', 3883, 5810, 3, 3884, 5812, 4),
(6127, 'NAICS', 1970, 7121, 3, 1977, 712190, 5),
(6128, 'SEC', 2617, 5400, 2, 2619, 5411, 4),
(6129, 'SIC', 4309, 40, 1, 3620, 4200, 2),
(6130, 'SIC', 4308, 20, 1, 3257, 2952, 4),
(6131, 'SEC', 2355, 3200, 2, 2362, 3240, 3),
(6132, 'NAICS', 1718, 55, 1, 1721, 55111, 4),
(6133, 'NAICS', 1792, 562, 2, 1801, 562212, 5),
(6134, 'SIC', 3480, 3600, 2, 3519, 3679, 4),
(6135, 'SIC', 3886, 5900, 2, 3888, 5912, 4),
(6136, 'NAICS', 1725, 56, 1, 1788, 561920, 5),
(6137, 'NAICS', 1591, 532, 2, 1615, 532412, 5),
(6138, 'SIC', 3762, 5100, 2, 3781, 5147, 4),
(6139, 'NAICS', 1913, 6233, 3, 1915, 623311, 5),
(6140, 'NAICS', 2037, 81, 1, 2104, 8131, 3),
(6141, 'NAICS', 1015, 424, 2, 1042, 424440, 5),
(6142, 'NAICS', 1952, 71119, 4, 1951, 711190, 5),
(6143, 'NAICS', 1672, 5416, 3, 1680, 54162, 4),
(6144, 'NAICS', 1640, 5413, 3, 1653, 541370, 5),
(6145, 'NAICS', 2120, 8139, 3, 2130, 81399, 4),
(6146, 'NAICS', 1624, 54, 1, 1678, 541618, 5),
(6147, 'SEC', 2687, 6360, 3, 2688, 6361, 4),
(6148, 'SIC', 3977, 6500, 2, 3979, 6512, 4),
(6149, 'SIC', 3371, 3400, 2, 3414, 3495, 4),
(6150, 'NAICS', 1624, 54, 1, 1715, 54194, 4),
(6151, 'NAICS', 1526, 5239, 3, 1533, 52399, 4),
(6152, 'SIC', 4308, 20, 1, 3283, 3110, 3),
(6153, 'SIC', 3480, 3600, 2, 3483, 3613, 4),
(6154, 'SIC', 3214, 2800, 2, 3219, 2819, 4),
(6155, 'SEC', 2792, 40, 1, 2534, 4600, 2),
(6156, 'SIC', 3214, 2800, 2, 3228, 2835, 4),
(6157, 'SEC', 2794, 52, 1, 2614, 5331, 4),
(6158, 'NAICS', 1942, 71, 1, 1987, 71321, 4),
(6159, 'SEC', 2476, 3800, 2, 2499, 3873, 4),
(6160, 'SIC', 3917, 6000, 2, 3923, 6022, 4),
(6161, 'NAICS', 36, 1114, 3, 40, 11142, 4),
(6162, 'SEC', 2323, 2830, 3, 2325, 2834, 4),
(6163, 'SIC', 4308, 20, 1, 3261, 3000, 2),
(6164, 'SIC', 4058, 7350, 3, 4060, 7353, 4),
(6165, 'NAICS', 1513, 523, 2, 1526, 5239, 3),
(6166, 'NAICS', 2151, 9221, 3, 2155, 92212, 4),
(6167, 'SIC', 4146, 8000, 2, 4152, 8031, 4),
(6168, 'NAICS', 1523, 5232, 3, 1525, 52321, 4),
(6169, 'NAICS', 1624, 54, 1, 1708, 54191, 4),
(6170, 'NAICS', 1850, 62, 1, 1924, 624120, 5),
(6171, 'NAICS', 2003, 72, 1, 2033, 722511, 5),
(6172, 'SEC', 2355, 3200, 2, 2361, 3231, 4),
(6173, 'SEC', 2526, 4500, 2, 2528, 4512, 4),
(6174, 'NAICS', 260, 2383, 3, 263, 238320, 5),
(6175, 'SEC', 2376, 3330, 3, 2377, 3334, 4),
(6176, 'SEC', 2640, 5900, 2, 2647, 5961, 4),
(6177, 'SEC', 2540, 4810, 3, 2542, 4813, 4),
(6178, 'SIC', 4179, 8210, 3, 4180, 8211, 4),
(6179, 'SEC', 2342, 3000, 2, 2348, 3060, 3),
(6180, 'NAICS', 1569, 53, 1, 1617, 53242, 4),
(6181, 'SIC', 3863, 5650, 3, 3864, 5651, 4),
(6182, 'SEC', 2794, 52, 1, 2644, 5944, 4),
(6183, 'SIC', 3073, 2280, 3, 3074, 2281, 4),
(6184, 'SIC', 4308, 20, 1, 3426, 3530, 3),
(6185, 'SIC', 3000, 2040, 3, 3006, 2047, 4),
(6186, 'SIC', 4313, 70, 1, 4114, 7810, 3),
(6187, 'SIC', 3511, 3670, 3, 3515, 3675, 4),
(6188, 'SIC', 3337, 3300, 2, 3366, 3366, 4),
(6189, 'SIC', 4308, 20, 1, 3307, 3230, 3),
(6190, 'SIC', 4310, 50, 1, 3758, 5092, 4),
(6191, 'NAICS', 1533, 52399, 4, 1535, 523999, 5),
(6192, 'SIC', 2987, 2020, 3, 2989, 2022, 4),
(6193, 'SEC', 2537, 4730, 3, 2538, 4731, 4),
(6194, 'NAICS', 218, 237, 2, 222, 237120, 5),
(6195, 'SEC', 2793, 50, 1, 2598, 5150, 3),
(6196, 'SIC', 3715, 5000, 2, 3755, 5088, 4),
(6197, 'NAICS', 1656, 54138, 4, 1655, 541380, 5),
(6198, 'NAICS', 1859, 6213, 3, 1865, 62133, 4),
(6199, 'NAICS', 1459, 5174, 3, 1461, 51741, 4),
(6200, 'NAICS', 1591, 532, 2, 1610, 532310, 5),
(6201, 'SEC', 2245, 2020, 3, 2246, 2024, 4),
(6202, 'SEC', 2791, 20, 1, 2450, 3670, 3),
(6203, 'SIC', 3214, 2800, 2, 3225, 2830, 3),
(6204, 'NAICS', 1720, 5511, 3, 1723, 551112, 5),
(6205, 'SIC', 4308, 20, 1, 3179, 2657, 4),
(6206, 'SIC', 4309, 40, 1, 3629, 4225, 4),
(6207, 'NAICS', 1683, 5417, 3, 1684, 54171, 4),
(6208, 'SEC', 2796, 70, 1, 2755, 8011, 4),
(6209, 'SIC', 4308, 20, 1, 3354, 3341, 4),
(6210, 'NAICS', 930, 42, 1, 1071, 4248, 3),
(6211, 'NAICS', 1635, 54121, 4, 1638, 541214, 5),
(6212, 'NAICS', 1725, 56, 1, 1785, 5619, 3),
(6213, 'SIC', 3419, 3500, 2, 3445, 3552, 4),
(6214, 'SIC', 4308, 20, 1, 3320, 3264, 4),
(6215, 'NAICS', 1475, 51912, 4, 1474, 519120, 5),
(6216, 'SEC', 2791, 20, 1, 2280, 2450, 3),
(6217, 'SIC', 4101, 7620, 3, 4104, 7629, 4),
(6218, 'SEC', 2777, 8730, 3, 2779, 8734, 4),
(6219, 'SIC', 4309, 40, 1, 3708, 4952, 4),
(6220, 'SIC', 2884, 1000, 2, 2896, 1080, 3),
(6221, 'SIC', 4308, 20, 1, 3570, 3850, 3),
(6222, 'SIC', 4306, 10, 1, 2935, 1480, 3),
(6223, 'NAICS', 991, 4238, 3, 1003, 42386, 4),
(6224, 'NAICS', 930, 42, 1, 1064, 424690, 5),
(6225, 'SIC', 4309, 40, 1, 3616, 4150, 3),
(6226, 'NAICS', 1689, 5418, 3, 1696, 541840, 5),
(6227, 'SEC', 2265, 2220, 3, 2266, 2221, 4),
(6228, 'SEC', 2694, 6500, 2, 2702, 6552, 4),
(6229, 'SIC', 3071, 2270, 3, 3072, 2273, 4),
(6230, 'NAICS', 1813, 611, 2, 1817, 6112, 3),
(6231, 'NAICS', 1, 11, 1, 40, 11142, 4),
(6232, 'NAICS', 1725, 56, 1, 1786, 561910, 5),
(6233, 'NAICS', 1725, 56, 1, 1796, 562112, 5),
(6234, 'NAICS', 2002, 71399, 4, 2001, 713990, 5),
(6235, 'SIC', 4313, 70, 1, 4201, 8390, 3),
(6236, 'NAICS', 2071, 812, 2, 2072, 8121, 3),
(6237, 'SIC', 4308, 20, 1, 3485, 3621, 4),
(6238, 'NAICS', 2010, 72119, 4, 2011, 721191, 5),
(6239, 'NAICS', 236, 2381, 3, 244, 23814, 4),
(6240, 'SIC', 2948, 1600, 2, 2950, 1611, 4),
(6241, 'SEC', 2292, 2600, 2, 2295, 2620, 3),
(6242, 'SEC', 2791, 20, 1, 2395, 3448, 4),
(6243, 'NAICS', 2151, 9221, 3, 2162, 922160, 5),
(6244, 'NAICS', 1435, 51222, 4, 1434, 512220, 5),
(6245, 'SEC', 2748, 7900, 2, 2751, 7990, 3),
(6246, 'NAICS', 1404, 5111, 3, 1414, 511191, 5),
(6247, 'NAICS', 2, 111, 2, 11, 11114, 4),
(6248, 'NAICS', 235, 238, 2, 256, 238220, 5),
(6249, 'NAICS', 991, 4238, 3, 994, 423820, 5),
(6250, 'NAICS', 235, 238, 2, 250, 23817, 4),
(6251, 'NAICS', 2166, 923, 2, 2175, 92314, 4),
(6252, 'SIC', 4018, 7210, 3, 4021, 7213, 4),
(6253, 'NAICS', 1480, 52, 1, 1545, 524130, 5),
(6254, 'NAICS', 2037, 81, 1, 2080, 8122, 3),
(6255, 'SIC', 3639, 4420, 3, 3640, 4424, 4),
(6256, 'NAICS', 236, 2381, 3, 243, 238140, 5),
(6257, 'SEC', 2221, 1300, 2, 2226, 1382, 4),
(6258, 'NAICS', 1625, 541, 2, 1703, 54187, 4),
(6259, 'NAICS', 1726, 561, 2, 1787, 56191, 4),
(6260, 'NAICS', 2037, 81, 1, 2066, 81142, 4),
(6261, 'SIC', 4192, 8300, 2, 4196, 8331, 4),
(6262, 'SEC', 2605, 5200, 2, 2606, 5210, 3),
(6263, 'NAICS', 1480, 52, 1, 1519, 523130, 5),
(6264, 'NAICS', 2005, 7211, 3, 2008, 721120, 5),
(6265, 'SIC', 3552, 3800, 2, 3573, 3861, 4),
(6266, 'NAICS', 1015, 424, 2, 1056, 42451, 4),
(6267, 'NAICS', 930, 42, 1, 1080, 42492, 4),
(6268, 'SIC', 3480, 3600, 2, 3482, 3612, 4),
(6269, 'SIC', 3978, 6510, 3, 3984, 6519, 4),
(6270, 'NAICS', 1920, 624, 2, 1928, 6242, 3),
(6271, 'NAICS', 2037, 81, 1, 2093, 8129, 3),
(6272, 'NAICS', 1766, 5616, 3, 1770, 561613, 5),
(6273, 'NAICS', 1942, 71, 1, 1959, 711310, 5),
(6274, 'SIC', 4314, 90, 1, 4284, 9600, 2),
(6275, 'SIC', 3050, 2200, 2, 3075, 2282, 4),
(6276, 'SIC', 2813, 170, 3, 2819, 179, 4),
(6277, 'SEC', 2500, 3900, 2, 2505, 3940, 3),
(6278, 'SIC', 3419, 3500, 2, 3467, 3579, 4),
(6279, 'SIC', 4313, 70, 1, 4109, 7690, 3),
(6280, 'SIC', 2918, 1400, 2, 2931, 1470, 3),
(6281, 'NAICS', 1813, 611, 2, 1843, 61169, 4),
(6282, 'SIC', 4311, 52, 1, 3842, 5530, 3),
(6283, 'NAICS', 1536, 524, 2, 1544, 524128, 5),
(6284, 'NAICS', 205, 23, 1, 227, 237210, 5),
(6285, 'SEC', 2791, 20, 1, 2417, 3559, 4),
(6286, 'NAICS', 931, 423, 2, 955, 4234, 3),
(6287, 'SEC', 2355, 3200, 2, 2356, 3210, 3),
(6288, 'SIC', 4308, 20, 1, 3099, 2341, 4),
(6289, 'SIC', 4308, 20, 1, 3514, 3674, 4),
(6290, 'SIC', 4309, 40, 1, 3606, 4110, 3),
(6291, 'SIC', 4313, 70, 1, 4210, 8611, 4),
(6292, 'NAICS', 252, 23819, 4, 251, 238190, 5),
(6293, 'SEC', 2791, 20, 1, 2318, 2790, 3),
(6294, 'SEC', 2500, 3900, 2, 2503, 3930, 3),
(6295, 'SIC', 4310, 50, 1, 3727, 5033, 4),
(6296, 'NAICS', 1969, 712, 2, 1970, 7121, 3),
(6297, 'SIC', 2982, 2000, 2, 3017, 2066, 4),
(6298, 'SIC', 4040, 7300, 2, 4068, 7373, 4),
(6299, 'NAICS', 1480, 52, 1, 1503, 522293, 5),
(6300, 'NAICS', 108, 114, 2, 111, 114111, 5),
(6301, 'SIC', 2798, 100, 2, 2817, 174, 4),
(6302, 'NAICS', 1480, 52, 1, 1540, 524114, 5),
(6303, 'NAICS', 1015, 424, 2, 1020, 42412, 4),
(6304, 'SIC', 4311, 52, 1, 3846, 5550, 3),
(6305, 'NAICS', 1569, 53, 1, 1598, 5322, 3),
(6306, 'NAICS', 2150, 922, 2, 2154, 922120, 5),
(6307, 'SIC', 2919, 1410, 3, 2920, 1411, 4),
(6308, 'SIC', 4312, 60, 1, 3963, 6324, 4),
(6309, 'SIC', 4313, 70, 1, 4149, 8020, 3),
(6310, 'SIC', 2868, 800, 2, 2869, 810, 3),
(6311, 'SEC', 2753, 8000, 2, 2763, 8082, 4),
(6312, 'NAICS', 2021, 7223, 3, 2026, 722330, 5),
(6313, 'NAICS', 2135, 92, 1, 2146, 921150, 5),
(6314, 'SIC', 3337, 3300, 2, 3354, 3341, 4),
(6315, 'SIC', 4313, 70, 1, 4237, 8742, 4),
(6316, 'NAICS', 1817, 6112, 3, 1818, 611210, 5),
(6317, 'NAICS', 79, 1124, 3, 82, 112420, 5),
(6318, 'SIC', 4305, 1, 1, 2838, 254, 4),
(6319, 'NAICS', 1035, 4244, 3, 1041, 42443, 4),
(6320, 'NAICS', 2021, 7223, 3, 2024, 722320, 5),
(6321, 'SIC', 3086, 2320, 3, 3088, 2322, 4),
(6322, 'NAICS', 138, 212, 2, 139, 2121, 3),
(6323, 'NAICS', 2028, 7224, 3, 2029, 722410, 5),
(6324, 'SEC', 2791, 20, 1, 2342, 3000, 2),
(6325, 'SIC', 4256, 9200, 2, 4261, 9222, 4),
(6326, 'SIC', 3190, 2700, 2, 3206, 2770, 3),
(6327, 'NAICS', 1569, 53, 1, 1584, 53131, 4),
(6328, 'NAICS', 1004, 4239, 3, 1014, 42399, 4),
(6329, 'NAICS', 1443, 5151, 3, 1445, 515111, 5),
(6330, 'NAICS', 1812, 61, 1, 1820, 6113, 3),
(6331, 'SIC', 4308, 20, 1, 3538, 3731, 4),
(6332, 'SIC', 3468, 3580, 3, 3473, 3589, 4),
(6333, 'SIC', 4223, 8700, 2, 4224, 8710, 3),
(6334, 'SIC', 3805, 5210, 3, 3806, 5211, 4),
(6335, 'NAICS', 1015, 424, 2, 1036, 424410, 5),
(6336, 'NAICS', 941, 4232, 3, 942, 423210, 5),
(6337, 'NAICS', 1624, 54, 1, 1703, 54187, 4),
(6338, 'SIC', 4308, 20, 1, 3366, 3366, 4),
(6339, 'SIC', 3693, 4900, 2, 3701, 4930, 3),
(6340, 'NAICS', 2003, 72, 1, 2030, 72241, 4),
(6341, 'SIC', 2975, 1790, 3, 2981, 1799, 4),
(6342, 'NAICS', 1625, 541, 2, 1708, 54191, 4),
(6343, 'SEC', 2791, 20, 1, 2295, 2620, 3),
(6344, 'SIC', 4040, 7300, 2, 4065, 7370, 3),
(6345, 'NAICS', 1798, 5622, 3, 1802, 562213, 5),
(6346, 'SIC', 4308, 20, 1, 3252, 2900, 2),
(6347, 'NAICS', 1569, 53, 1, 1573, 53111, 4),
(6348, 'NAICS', 931, 423, 2, 953, 423390, 5),
(6349, 'SIC', 4171, 8090, 3, 4172, 8092, 4),
(6350, 'NAICS', 132, 21, 1, 178, 213114, 5),
(6351, 'SIC', 4308, 20, 1, 3090, 2325, 4),
(6352, 'NAICS', 931, 423, 2, 962, 423440, 5),
(6353, 'NAICS', 2037, 81, 1, 2046, 811121, 5),
(6354, 'NAICS', 930, 42, 1, 943, 42321, 4),
(6355, 'SIC', 4309, 40, 1, 3604, 4013, 4),
(6356, 'NAICS', 1859, 6213, 3, 1866, 621340, 5),
(6357, 'SIC', 4308, 20, 1, 3246, 2890, 3),
(6358, 'NAICS', 1625, 541, 2, 1715, 54194, 4),
(6359, 'NAICS', 1402, 51, 1, 1431, 5122, 3),
(6360, 'SIC', 4308, 20, 1, 3281, 3089, 4),
(6361, 'SEC', 2403, 3500, 2, 2413, 3540, 3),
(6362, 'NAICS', 1015, 424, 2, 1077, 424910, 5),
(6363, 'NAICS', 181, 221, 2, 196, 221210, 5),
(6364, 'NAICS', 1836, 6116, 3, 1837, 611610, 5),
(6365, 'SIC', 4081, 7500, 2, 4084, 7514, 4),
(6366, 'SIC', 4125, 7900, 2, 4142, 7993, 4),
(6367, 'SEC', 2552, 4900, 2, 2567, 4961, 4),
(6368, 'NAICS', 930, 42, 1, 982, 4237, 3),
(6369, 'SEC', 2793, 50, 1, 2581, 5064, 4),
(6370, 'SIC', 3311, 3250, 3, 3314, 3255, 4),
(6371, 'SIC', 4244, 8900, 2, 4246, 8999, 4),
(6372, 'SEC', 2440, 3630, 3, 2441, 3634, 4),
(6373, 'SIC', 3822, 5400, 2, 3833, 5460, 3),
(6374, 'SEC', 2791, 20, 1, 2287, 2522, 4),
(6375, 'NAICS', 1891, 62199, 4, 1892, 621991, 5),
(6376, 'NAICS', 2052, 8112, 3, 2057, 811219, 5),
(6377, 'SIC', 4308, 20, 1, 3114, 2389, 4),
(6378, 'NAICS', 1812, 61, 1, 1828, 611430, 5),
(6379, 'SIC', 4307, 15, 1, 2955, 1700, 2),
(6380, 'SIC', 4313, 70, 1, 4239, 8744, 4),
(6381, 'NAICS', 1758, 5615, 3, 1762, 56152, 4),
(6382, 'SIC', 2983, 2010, 3, 2985, 2013, 4),
(6383, 'SEC', 2585, 5080, 3, 2587, 5084, 4),
(6384, 'SIC', 3527, 3710, 3, 3530, 3714, 4),
(6385, 'SEC', 2319, 2800, 2, 2322, 2821, 4),
(6386, 'NAICS', 1793, 5621, 3, 1794, 56211, 4),
(6387, 'SIC', 3307, 3230, 3, 3308, 3231, 4),
(6388, 'NAICS', 2037, 81, 1, 2094, 812910, 5),
(6389, 'SIC', 4308, 20, 1, 3206, 2770, 3),
(6390, 'SIC', 4313, 70, 1, 4012, 7030, 3),
(6391, 'SEC', 2328, 2840, 3, 2330, 2844, 4),
(6392, 'SIC', 3371, 3400, 2, 3395, 3460, 3),
(6393, 'NAICS', 2189, 9261, 3, 2190, 926110, 5),
(6394, 'SIC', 4311, 52, 1, 3838, 5510, 3),
(6395, 'SIC', 3882, 5800, 2, 3884, 5812, 4),
(6396, 'NAICS', 930, 42, 1, 1034, 42434, 4),
(6397, 'NAICS', 1726, 561, 2, 1728, 561110, 5),
(6398, 'NAICS', 2136, 921, 2, 2140, 921120, 5),
(6399, 'SEC', 2791, 20, 1, 2451, 3672, 4),
(6400, 'SEC', 2552, 4900, 2, 2555, 4920, 3),
(6401, 'SIC', 4311, 52, 1, 3834, 5461, 4),
(6402, 'NAICS', 1942, 71, 1, 1956, 711212, 5),
(6403, 'SIC', 2834, 250, 3, 2835, 251, 4),
(6404, 'NAICS', 1682, 54169, 4, 1681, 541690, 5),
(6405, 'NAICS', 2038, 811, 2, 2064, 811412, 5),
(6406, 'SIC', 4306, 10, 1, 2938, 1499, 4),
(6407, 'SIC', 4133, 7940, 3, 4134, 7941, 4),
(6408, 'NAICS', 108, 114, 2, 115, 114210, 5),
(6409, 'NAICS', 1480, 52, 1, 1514, 5231, 3),
(6410, 'NAICS', 1, 11, 1, 79, 1124, 3),
(6411, 'SIC', 4223, 8700, 2, 4226, 8712, 4),
(6412, 'SEC', 2403, 3500, 2, 2417, 3559, 4),
(6413, 'NAICS', 1554, 525, 2, 1566, 52592, 4),
(6414, 'SEC', 2713, 7300, 2, 2715, 7311, 4),
(6415, 'SEC', 2795, 60, 1, 2656, 6036, 4),
(6416, 'SIC', 3480, 3600, 2, 3486, 3624, 4),
(6417, 'NAICS', 273, 2389, 3, 277, 23899, 4),
(6418, 'SIC', 3511, 3670, 3, 3514, 3674, 4),
(6419, 'NAICS', 1485, 522, 2, 1500, 52229, 4),
(6420, 'NAICS', 1648, 54134, 4, 1647, 541340, 5),
(6421, 'NAICS', 1591, 532, 2, 1599, 532210, 5),
(6422, 'SIC', 3583, 3940, 3, 3584, 3942, 4),
(6423, 'NAICS', 157, 21231, 4, 160, 212313, 5),
(6424, 'NAICS', 1942, 71, 1, 1983, 713120, 5),
(6425, 'SIC', 4305, 1, 1, 2816, 173, 4),
(6426, 'SIC', 2813, 170, 3, 2818, 175, 4),
(6427, 'NAICS', 1920, 624, 2, 1922, 624110, 5),
(6428, 'SIC', 4259, 9220, 3, 4261, 9222, 4),
(6429, 'NAICS', 948, 42331, 4, 947, 423310, 5),
(6430, 'NAICS', 1920, 624, 2, 1933, 624229, 5),
(6431, 'NAICS', 1598, 5322, 3, 1606, 532291, 5),
(6432, 'NAICS', 109, 1141, 3, 113, 114119, 5),
(6433, 'SIC', 2955, 1700, 2, 2971, 1770, 3),
(6434, 'SIC', 3148, 2500, 2, 3160, 2531, 4),
(6435, 'SIC', 4017, 7200, 2, 4037, 7290, 3),
(6436, 'SIC', 3008, 2050, 3, 3011, 2053, 4),
(6437, 'SEC', 2434, 3600, 2, 2451, 3672, 4),
(6438, 'NAICS', 1726, 561, 2, 1729, 56111, 4),
(6439, 'NAICS', 218, 237, 2, 232, 2379, 3),
(6440, 'NAICS', 1569, 53, 1, 1592, 5321, 3),
(6441, 'NAICS', 2003, 72, 1, 2017, 7213, 3),
(6442, 'NAICS', 2135, 92, 1, 2171, 92312, 4),
(6443, 'SIC', 4311, 52, 1, 3875, 5720, 3),
(6444, 'SEC', 4336, 99, 1, 4339, 9995, 2),
(6445, 'NAICS', 1, 11, 1, 14, 111160, 5),
(6446, 'SEC', 2794, 52, 1, 2641, 5910, 3),
(6447, 'SIC', 4308, 20, 1, 3299, 3190, 3),
(6448, 'SIC', 2825, 200, 2, 2833, 241, 4),
(6449, 'NAICS', 108, 114, 2, 114, 1142, 3),
(6450, 'SIC', 3419, 3500, 2, 3440, 3546, 4),
(6451, 'NAICS', 2037, 81, 1, 2129, 813990, 5),
(6452, 'SIC', 3083, 2300, 2, 3097, 2339, 4),
(6453, 'SIC', 3605, 4100, 2, 3614, 4141, 4),
(6454, 'NAICS', 132, 21, 1, 163, 212321, 5),
(6455, 'NAICS', 1625, 541, 2, 1678, 541618, 5),
(6456, 'NAICS', 135, 21111, 4, 136, 211111, 5),
(6457, 'NAICS', 28, 11133, 4, 29, 111331, 5),
(6458, 'NAICS', 1480, 52, 1, 1558, 525120, 5),
(6459, 'SIC', 3774, 5140, 3, 3778, 5144, 4),
(6460, 'SEC', 2791, 20, 1, 2495, 3851, 4),
(6461, 'SIC', 3992, 6700, 2, 4000, 6732, 4),
(6462, 'NAICS', 57, 1121, 3, 64, 11213, 4),
(6463, 'NAICS', 991, 4238, 3, 1002, 423860, 5),
(6464, 'SEC', 2794, 52, 1, 2618, 5410, 3),
(6465, 'SIC', 4308, 20, 1, 3168, 2610, 3),
(6466, 'SEC', 2791, 20, 1, 2357, 3211, 4),
(6467, 'SIC', 4169, 8080, 3, 4170, 8082, 4),
(6468, 'NAICS', 1537, 5241, 3, 1539, 524113, 5),
(6469, 'NAICS', 2150, 922, 2, 2153, 92211, 4),
(6470, 'SIC', 4284, 9600, 2, 4289, 9630, 3),
(6471, 'SIC', 4312, 60, 1, 3950, 6211, 4),
(6472, 'NAICS', 1979, 713, 2, 1997, 713940, 5),
(6473, 'NAICS', 1480, 52, 1, 1515, 523110, 5),
(6474, 'NAICS', 1624, 54, 1, 1666, 5415, 3),
(6475, 'NAICS', 132, 21, 1, 145, 212210, 5),
(6476, 'SIC', 4307, 15, 1, 2967, 1751, 4),
(6477, 'SIC', 2962, 1740, 3, 2964, 1742, 4),
(6478, 'SIC', 4310, 50, 1, 3791, 5170, 3),
(6479, 'NAICS', 1624, 54, 1, 1696, 541840, 5),
(6480, 'SIC', 3434, 3540, 3, 3435, 3541, 4),
(6481, 'NAICS', 2037, 81, 1, 2073, 81211, 4),
(6482, 'NAICS', 1480, 52, 1, 1523, 5232, 3),
(6483, 'SIC', 4312, 60, 1, 3970, 6370, 3),
(6484, 'SIC', 4312, 60, 1, 3969, 6361, 4),
(6485, 'NAICS', 56, 112, 2, 77, 112390, 5),
(6486, 'SEC', 2791, 20, 1, 2368, 3280, 3),
(6487, 'NAICS', 1015, 424, 2, 1025, 42421, 4),
(6488, 'NAICS', 1, 11, 1, 76, 11234, 4),
(6489, 'SIC', 3602, 4010, 3, 3604, 4013, 4),
(6490, 'NAICS', 218, 237, 2, 221, 23711, 4),
(6491, 'SEC', 2791, 20, 1, 2297, 2630, 3),
(6492, 'SEC', 2337, 2900, 2, 2340, 2950, 3),
(6493, 'SIC', 3680, 4800, 2, 3692, 4899, 4),
(6494, 'NAICS', 1953, 7112, 3, 1956, 711212, 5),
(6495, 'SIC', 4308, 20, 1, 3595, 3990, 3),
(6496, 'SIC', 3762, 5100, 2, 3797, 5190, 3),
(6497, 'SEC', 2739, 7810, 3, 2741, 7819, 4),
(6498, 'NAICS', 1980, 7131, 3, 1981, 713110, 5),
(6499, 'NAICS', 1725, 56, 1, 1800, 562211, 5),
(6500, 'SIC', 3587, 3950, 3, 3589, 3952, 4),
(6501, 'SEC', 2790, 15, 1, 2233, 1540, 3),
(6502, 'SEC', 2342, 3000, 2, 2351, 3086, 4),
(6503, 'SEC', 2240, 2000, 2, 2252, 2060, 3),
(6504, 'SEC', 2791, 20, 1, 2500, 3900, 2),
(6505, 'SEC', 2371, 3300, 2, 2382, 3360, 3),
(6506, 'SIC', 3621, 4210, 3, 3624, 4214, 4),
(6507, 'SEC', 2725, 7370, 3, 2727, 7372, 4),
(6508, 'SEC', 2791, 20, 1, 2413, 3540, 3),
(6509, 'NAICS', 43, 1119, 3, 46, 111920, 5),
(6510, 'SIC', 4308, 20, 1, 3134, 2435, 4),
(6511, 'SIC', 3033, 2090, 3, 3036, 2095, 4),
(6512, 'SEC', 2620, 5500, 2, 2621, 5530, 3),
(6513, 'SIC', 4223, 8700, 2, 4227, 8713, 4),
(6514, 'NAICS', 2, 111, 2, 48, 111930, 5),
(6515, 'SEC', 2640, 5900, 2, 2642, 5912, 4),
(6516, 'SIC', 4309, 40, 1, 3700, 4925, 4),
(6517, 'SEC', 2302, 2700, 2, 2309, 2732, 4),
(6518, 'SIC', 3419, 3500, 2, 3438, 3544, 4),
(6519, 'SIC', 4310, 50, 1, 3736, 5049, 4),
(6520, 'SIC', 4313, 70, 1, 4115, 7812, 4),
(6521, 'SIC', 4306, 10, 1, 2889, 1030, 3),
(6522, 'SIC', 4308, 20, 1, 3576, 3900, 2),
(6523, 'SIC', 4308, 20, 1, 3187, 2677, 4),
(6524, 'SIC', 4211, 8620, 3, 4212, 8621, 4),
(6525, 'NAICS', 229, 2373, 3, 231, 23731, 4),
(6526, 'SIC', 3301, 3200, 2, 3325, 3273, 4),
(6527, 'SEC', 2791, 20, 1, 2380, 3350, 3),
(6528, 'SIC', 4307, 15, 1, 2953, 1623, 4),
(6529, 'SIC', 3774, 5140, 3, 3783, 5149, 4),
(6530, 'NAICS', 930, 42, 1, 1055, 424510, 5),
(6531, 'NAICS', 260, 2383, 3, 265, 238330, 5),
(6532, 'NAICS', 180, 22, 1, 185, 221112, 5),
(6533, 'SIC', 3451, 3560, 3, 3456, 3565, 4),
(6534, 'NAICS', 1732, 56121, 4, 1731, 561210, 5),
(6535, 'SIC', 4123, 7840, 3, 4124, 7841, 4),
(6536, 'SIC', 3337, 3300, 2, 3368, 3390, 3),
(6537, 'NAICS', 2037, 81, 1, 2102, 81299, 4),
(6538, 'NAICS', 2151, 9221, 3, 2152, 922110, 5),
(6539, 'SEC', 2241, 2010, 3, 2242, 2011, 4),
(6540, 'SIC', 3301, 3200, 2, 3321, 3269, 4),
(6541, 'NAICS', 2176, 924, 2, 2181, 92412, 4),
(6542, 'SIC', 2960, 1730, 3, 2961, 1731, 4),
(6543, 'NAICS', 1948, 71112, 4, 1947, 711120, 5),
(6544, 'NAICS', 1942, 71, 1, 1965, 71141, 4),
(6545, 'SIC', 4313, 70, 1, 4072, 7377, 4),
(6546, 'NAICS', 1536, 524, 2, 1550, 52429, 4),
(6547, 'NAICS', 1570, 531, 2, 1577, 53113, 4),
(6548, 'SIC', 3148, 2500, 2, 3152, 2514, 4),
(6549, 'SIC', 3715, 5000, 2, 3729, 5040, 3),
(6550, 'SIC', 3337, 3300, 2, 3363, 3363, 4),
(6551, 'NAICS', 2061, 8114, 3, 2067, 811430, 5),
(6552, 'SIC', 4308, 20, 1, 3414, 3495, 4),
(6553, 'SIC', 4308, 20, 1, 3493, 3634, 4),
(6554, 'NAICS', 56, 112, 2, 64, 11213, 4),
(6555, 'NAICS', 1477, 51913, 4, 1476, 519130, 5),
(6556, 'SIC', 2880, 920, 3, 2881, 921, 4),
(6557, 'NAICS', 1799, 56221, 4, 1802, 562213, 5),
(6558, 'SEC', 2640, 5900, 2, 2646, 5960, 3),
(6559, 'NAICS', 2037, 81, 1, 2042, 811112, 5),
(6560, 'NAICS', 1693, 54182, 4, 1692, 541820, 5),
(6561, 'NAICS', 1808, 56292, 4, 1807, 562920, 5),
(6562, 'SIC', 3564, 3840, 3, 3566, 3842, 4),
(6563, 'NAICS', 28, 11133, 4, 30, 111332, 5),
(6564, 'SEC', 2355, 3200, 2, 2367, 3272, 4),
(6565, 'NAICS', 1891, 62199, 4, 1893, 621999, 5),
(6566, 'SIC', 3067, 2260, 3, 3070, 2269, 4),
(6567, 'SIC', 4308, 20, 1, 3105, 2369, 4),
(6568, 'NAICS', 56, 112, 2, 57, 1121, 3),
(6569, 'NAICS', 1867, 62134, 4, 1866, 621340, 5),
(6570, 'NAICS', 1936, 6243, 3, 1937, 624310, 5),
(6571, 'SEC', 2694, 6500, 2, 4326, 6532, 3),
(6572, 'SIC', 4308, 20, 1, 3064, 2257, 4),
(6573, 'SIC', 4310, 50, 1, 3743, 5065, 4),
(6574, 'NAICS', 1075, 42482, 4, 1074, 424820, 5),
(6575, 'SIC', 3282, 3100, 2, 3284, 3111, 4),
(6576, 'SIC', 2982, 2000, 2, 3023, 2076, 4),
(6577, 'SIC', 4309, 40, 1, 3612, 4131, 4),
(6578, 'NAICS', 235, 238, 2, 249, 238170, 5),
(6579, 'NAICS', 1624, 54, 1, 1693, 54182, 4),
(6580, 'SEC', 2630, 5700, 2, 2633, 5730, 3),
(6581, 'NAICS', 1726, 561, 2, 1776, 56171, 4),
(6582, 'SEC', 2791, 20, 1, 2256, 2086, 4),
(6583, 'SIC', 3419, 3500, 2, 3455, 3564, 4),
(6584, 'NAICS', 132, 21, 1, 151, 212231, 5),
(6585, 'NAICS', 1726, 561, 2, 1733, 5613, 3),
(6586, 'SIC', 4178, 8200, 2, 4189, 8249, 4),
(6587, 'SIC', 4309, 40, 1, 3652, 4493, 4),
(6588, 'SIC', 4008, 7010, 3, 4009, 7011, 4),
(6589, 'NAICS', 1485, 522, 2, 1489, 522120, 5),
(6590, 'NAICS', 2030, 72241, 4, 2029, 722410, 5),
(6591, 'SIC', 3762, 5100, 2, 3769, 5130, 3),
(6592, 'NAICS', 955, 4234, 3, 957, 42341, 4),
(6593, 'NAICS', 1849, 61171, 4, 1848, 611710, 5),
(6594, 'NAICS', 205, 23, 1, 207, 2361, 3),
(6595, 'NAICS', 1410, 51113, 4, 1409, 511130, 5),
(6596, 'SIC', 3214, 2800, 2, 3231, 2841, 4),
(6597, 'NAICS', 1979, 713, 2, 1989, 71329, 4),
(6598, 'NAICS', 1482, 5211, 3, 1484, 52111, 4),
(6599, 'SIC', 4314, 90, 1, 4265, 9300, 2),
(6600, 'NAICS', 1982, 71311, 4, 1981, 713110, 5),
(6601, 'NAICS', 2077, 81219, 4, 2078, 812191, 5),
(6602, 'SIC', 3141, 2450, 3, 3143, 2452, 4),
(6603, 'NAICS', 1914, 62331, 4, 1915, 623311, 5),
(6604, 'NAICS', 1726, 561, 2, 1777, 561720, 5),
(6605, 'NAICS', 2072, 8121, 3, 2073, 81211, 4),
(6606, 'SIC', 4040, 7300, 2, 4045, 7319, 4),
(6607, 'SIC', 4223, 8700, 2, 4228, 8720, 3),
(6608, 'SIC', 2834, 250, 3, 2837, 253, 4),
(6609, 'SEC', 2568, 5000, 2, 2584, 5072, 4),
(6610, 'NAICS', 931, 423, 2, 986, 42372, 4),
(6611, 'SEC', 2539, 4800, 2, 2540, 4810, 3),
(6612, 'SIC', 3026, 2080, 3, 3030, 2085, 4),
(6613, 'NAICS', 1508, 52231, 4, 1507, 522310, 5),
(6614, 'SIC', 3496, 3640, 3, 3502, 3647, 4),
(6615, 'SIC', 4313, 70, 1, 4221, 8690, 3),
(6616, 'SIC', 4313, 70, 1, 4246, 8999, 4),
(6617, 'NAICS', 1512, 52239, 4, 1511, 522390, 5),
(6618, 'NAICS', 1850, 62, 1, 1923, 62411, 4),
(6619, 'SIC', 4314, 90, 1, 4264, 9229, 4),
(6620, 'SIC', 3715, 5000, 2, 3739, 5052, 4),
(6621, 'NAICS', 961, 42343, 4, 960, 423430, 5),
(6622, 'SIC', 3917, 6000, 2, 3934, 6090, 3),
(6623, 'NAICS', 23, 1113, 3, 28, 11133, 4),
(6624, 'SIC', 4256, 9200, 2, 4263, 9224, 4),
(6625, 'NAICS', 1817, 6112, 3, 1819, 61121, 4),
(6626, 'SEC', 2366, 3270, 3, 2367, 3272, 4),
(6627, 'SIC', 3301, 3200, 2, 3334, 3296, 4),
(6628, 'SEC', 2302, 2700, 2, 2317, 2780, 3),
(6629, 'NAICS', 174, 21311, 4, 179, 213115, 5),
(6630, 'NAICS', 1480, 52, 1, 1568, 52599, 4),
(6631, 'NAICS', 1812, 61, 1, 1824, 611410, 5),
(6632, 'SEC', 2677, 6300, 2, 2679, 6311, 4),
(6633, 'NAICS', 1689, 5418, 3, 1702, 541870, 5),
(6634, 'NAICS', 2038, 811, 2, 2063, 811411, 5),
(6635, 'SIC', 4313, 70, 1, 4097, 7540, 3),
(6636, 'SIC', 2982, 2000, 2, 3018, 2067, 4),
(6637, 'NAICS', 930, 42, 1, 1090, 4251, 3),
(6638, 'NAICS', 1625, 541, 2, 1712, 541930, 5),
(6639, 'SIC', 3595, 3990, 3, 3598, 3995, 4),
(6640, 'SIC', 4308, 20, 1, 3221, 2821, 4),
(6641, 'NAICS', 1471, 5191, 3, 1473, 51911, 4),
(6642, 'SIC', 2884, 1000, 2, 2887, 1020, 3),
(6643, 'SIC', 3220, 2820, 3, 3221, 2821, 4),
(6644, 'NAICS', 2135, 92, 1, 2188, 926, 2),
(6645, 'NAICS', 235, 238, 2, 260, 2383, 3),
(6646, 'SEC', 2450, 3670, 3, 2453, 3677, 4),
(6647, 'SEC', 2793, 50, 1, 2599, 5160, 3),
(6648, 'NAICS', 1, 11, 1, 97, 11299, 4),
(6649, 'NAICS', 108, 114, 2, 116, 11421, 4),
(6650, 'SEC', 2795, 60, 1, 4340, 6172, 4),
(6651, 'SIC', 4308, 20, 1, 3296, 3170, 3),
(6652, 'SEC', 2791, 20, 1, 2359, 3221, 4),
(6653, 'NAICS', 1939, 6244, 3, 1941, 62441, 4),
(6654, 'NAICS', 2103, 813, 2, 2106, 81311, 4),
(6655, 'SIC', 4312, 60, 1, 3933, 6082, 4),
(6656, 'SIC', 4308, 20, 1, 3037, 2096, 4),
(6657, 'NAICS', 1725, 56, 1, 1771, 56162, 4),
(6658, 'SEC', 2362, 3240, 3, 2363, 3241, 4),
(6659, 'SIC', 3083, 2300, 2, 3101, 2350, 3),
(6660, 'SIC', 4308, 20, 1, 3030, 2085, 4),
(6661, 'SIC', 3434, 3540, 3, 3441, 3547, 4),
(6662, 'SIC', 4309, 40, 1, 3647, 4482, 4),
(6663, 'SIC', 3552, 3800, 2, 3553, 3810, 3),
(6664, 'SIC', 4308, 20, 1, 3265, 3021, 4),
(6665, 'SIC', 3977, 6500, 2, 3981, 6514, 4),
(6666, 'SEC', 2789, 10, 1, 2218, 1200, 2),
(6667, 'SIC', 4308, 20, 1, 3563, 3829, 4),
(6668, 'SIC', 3804, 5200, 2, 3809, 5250, 3),
(6669, 'NAICS', 2037, 81, 1, 2085, 8123, 3),
(6670, 'SEC', 2343, 3010, 3, 2344, 3011, 4),
(6671, 'NAICS', 2077, 81219, 4, 2079, 812199, 5),
(6672, 'SIC', 4235, 8740, 3, 4236, 8741, 4),
(6673, 'NAICS', 1461, 51741, 4, 1460, 517410, 5),
(6674, 'SIC', 4313, 70, 1, 4172, 8092, 4),
(6675, 'NAICS', 1481, 521, 2, 1482, 5211, 3),
(6676, 'SEC', 2791, 20, 1, 2426, 3572, 4),
(6677, 'SIC', 3813, 5270, 3, 3814, 5271, 4),
(6678, 'SEC', 2403, 3500, 2, 2424, 3570, 3),
(6679, 'NAICS', 2085, 8123, 3, 2090, 81233, 4),
(6680, 'SEC', 2791, 20, 1, 2449, 3669, 4),
(6681, 'SIC', 4313, 70, 1, 4218, 8651, 4),
(6682, 'SIC', 3355, 3350, 3, 3360, 3356, 4),
(6683, 'NAICS', 1402, 51, 1, 1410, 51113, 4),
(6684, 'SEC', 2793, 50, 1, 2583, 5070, 3),
(6685, 'SIC', 2982, 2000, 2, 2999, 2038, 4),
(6686, 'NAICS', 117, 115, 2, 120, 115111, 5),
(6687, 'NAICS', 1725, 56, 1, 1809, 56299, 4),
(6688, 'SIC', 4300, 9720, 3, 4301, 9721, 4),
(6689, 'SIC', 4308, 20, 1, 3174, 2650, 3),
(6690, 'SIC', 3959, 6310, 3, 3960, 6311, 4),
(6691, 'SIC', 3620, 4200, 2, 3621, 4210, 3),
(6692, 'SIC', 4017, 7200, 2, 4032, 7241, 4),
(6693, 'NAICS', 107, 11331, 4, 106, 113310, 5),
(6694, 'SIC', 3641, 4430, 3, 3642, 4432, 4),
(6695, 'SIC', 3869, 5700, 2, 3876, 5722, 4),
(6696, 'NAICS', 1624, 54, 1, 1667, 54151, 4),
(6697, 'SIC', 4114, 7810, 3, 4115, 7812, 4),
(6698, 'SIC', 2850, 720, 3, 2854, 724, 4),
(6699, 'NAICS', 1486, 5221, 3, 1488, 52211, 4),
(6700, 'NAICS', 1943, 711, 2, 1945, 711110, 5),
(6701, 'SIC', 3083, 2300, 2, 3098, 2340, 3),
(6702, 'NAICS', 2135, 92, 1, 2200, 927, 2),
(6703, 'NAICS', 1, 11, 1, 110, 11411, 4),
(6704, 'NAICS', 1851, 621, 2, 1890, 62191, 4),
(6705, 'NAICS', 1850, 62, 1, 1860, 621310, 5),
(6706, 'NAICS', 2003, 72, 1, 2007, 72111, 4),
(6707, 'SIC', 2918, 1400, 2, 2927, 1446, 4),
(6708, 'NAICS', 1944, 7111, 3, 1949, 711130, 5),
(6709, 'SIC', 4305, 1, 1, 2848, 710, 3),
(6710, 'SIC', 3371, 3400, 2, 3387, 3443, 4),
(6711, 'SEC', 2791, 20, 1, 2240, 2000, 2),
(6712, 'SIC', 4313, 70, 1, 4007, 7000, 2),
(6713, 'SIC', 4313, 70, 1, 4133, 7940, 3),
(6714, 'SIC', 4313, 70, 1, 4154, 8041, 4),
(6715, 'SIC', 4312, 60, 1, 3928, 6060, 3),
(6716, 'NAICS', 235, 238, 2, 272, 23839, 4),
(6717, 'SIC', 4312, 60, 1, 3927, 6036, 4),
(6718, 'NAICS', 1624, 54, 1, 1711, 541922, 5),
(6719, 'SEC', 2434, 3600, 2, 2449, 3669, 4),
(6720, 'NAICS', 205, 23, 1, 248, 23816, 4),
(6721, 'NAICS', 2037, 81, 1, 2081, 812210, 5),
(6722, 'SEC', 2319, 2800, 2, 2333, 2860, 3),
(6723, 'SIC', 4314, 90, 1, 4301, 9721, 4),
(6724, 'SIC', 4308, 20, 1, 3583, 3940, 3),
(6725, 'SIC', 2826, 210, 3, 2830, 214, 4),
(6726, 'NAICS', 930, 42, 1, 1061, 4246, 3),
(6727, 'NAICS', 1850, 62, 1, 1862, 621320, 5),
(6728, 'SIC', 2798, 100, 2, 2820, 180, 3),
(6729, 'NAICS', 1921, 6241, 3, 1926, 624190, 5),
(6730, 'NAICS', 930, 42, 1, 936, 42312, 4),
(6731, 'NAICS', 1612, 5324, 3, 1615, 532412, 5),
(6732, 'NAICS', 2120, 8139, 3, 2128, 81394, 4),
(6733, 'SIC', 4309, 40, 1, 3666, 4619, 4),
(6734, 'SIC', 4310, 50, 1, 3748, 5078, 4),
(6735, 'NAICS', 1904, 623, 2, 1911, 623220, 5),
(6736, 'NAICS', 1439, 51224, 4, 1438, 512240, 5),
(6737, 'NAICS', 1625, 541, 2, 1681, 541690, 5),
(6738, 'NAICS', 1812, 61, 1, 1834, 611513, 5),
(6739, 'SIC', 2909, 1300, 2, 2916, 1382, 4),
(6740, 'NAICS', 1625, 541, 2, 1640, 5413, 3),
(6741, 'SIC', 4309, 40, 1, 3685, 4822, 4),
(6742, 'NAICS', 1514, 5231, 3, 1522, 52314, 4),
(6743, 'NAICS', 1624, 54, 1, 1709, 54192, 4),
(6744, 'SIC', 2805, 130, 3, 2807, 132, 4),
(6745, 'NAICS', 1569, 53, 1, 1597, 53212, 4),
(6746, 'NAICS', 206, 236, 2, 209, 236115, 5),
(6747, 'SEC', 2458, 3700, 2, 2459, 3710, 3),
(6748, 'NAICS', 1830, 6115, 3, 1834, 611513, 5),
(6749, 'NAICS', 93, 11292, 4, 92, 112920, 5),
(6750, 'SIC', 3190, 2700, 2, 3212, 2791, 4),
(6751, 'SIC', 3261, 3000, 2, 3264, 3020, 3),
(6752, 'SIC', 4308, 20, 1, 3188, 2678, 4),
(6753, 'SIC', 3662, 4600, 2, 3663, 4610, 3),
(6754, 'NAICS', 139, 2121, 3, 142, 212112, 5),
(6755, 'SIC', 4306, 10, 1, 2937, 1490, 3),
(6756, 'SIC', 3214, 2800, 2, 3251, 2899, 4),
(6757, 'NAICS', 2103, 813, 2, 2105, 813110, 5),
(6758, 'SEC', 2566, 4960, 3, 2567, 4961, 4),
(6759, 'SIC', 4308, 20, 1, 3361, 3357, 4),
(6760, 'SIC', 4313, 70, 1, 4030, 7231, 4),
(6761, 'NAICS', 1942, 71, 1, 1977, 712190, 5),
(6762, 'SIC', 4308, 20, 1, 3468, 3580, 3),
(6763, 'NAICS', 118, 1151, 3, 120, 115111, 5),
(6764, 'NAICS', 1, 11, 1, 4, 111110, 5),
(6765, 'SIC', 4313, 70, 1, 4222, 8699, 4),
(6766, 'NAICS', 1725, 56, 1, 1744, 56142, 4),
(6767, 'SIC', 4308, 20, 1, 3397, 3463, 4),
(6768, 'SEC', 2530, 4520, 3, 2531, 4522, 4),
(6769, 'NAICS', 215, 23621, 4, 214, 236210, 5),
(6770, 'SIC', 4308, 20, 1, 3113, 2387, 4),
(6771, 'NAICS', 1420, 5121, 3, 1421, 512110, 5),
(6772, 'NAICS', 2150, 922, 2, 2165, 92219, 4),
(6773, 'SIC', 4308, 20, 1, 3208, 2780, 3),
(6774, 'SIC', 3156, 2520, 3, 3157, 2521, 4),
(6775, 'NAICS', 930, 42, 1, 1054, 4245, 3),
(6776, 'NAICS', 1792, 562, 2, 1799, 56221, 4),
(6777, 'NAICS', 1624, 54, 1, 1716, 541990, 5),
(6778, 'NAICS', 1850, 62, 1, 1869, 621391, 5),
(6779, 'NAICS', 1876, 62149, 4, 1878, 621492, 5),
(6780, 'SIC', 4313, 70, 1, 4127, 7911, 4),
(6781, 'SIC', 4312, 60, 1, 3920, 6019, 4),
(6782, 'NAICS', 1624, 54, 1, 1682, 54169, 4),
(6783, 'SIC', 3167, 2600, 2, 3182, 2672, 4),
(6784, 'SIC', 3214, 2800, 2, 3224, 2824, 4),
(6785, 'SIC', 3958, 6300, 2, 3973, 6399, 4),
(6786, 'NAICS', 238, 23811, 4, 237, 238110, 5),
(6787, 'SEC', 2796, 70, 1, 2780, 8740, 3),
(6788, 'SEC', 2735, 7500, 2, 2736, 7510, 3),
(6789, 'SEC', 2574, 5040, 3, 2576, 5047, 4),
(6790, 'SIC', 4308, 20, 1, 3015, 2063, 4),
(6791, 'SIC', 3526, 3700, 2, 3545, 3761, 4),
(6792, 'SEC', 2358, 3220, 3, 2359, 3221, 4),
(6793, 'SIC', 3520, 3690, 3, 3524, 3695, 4),
(6794, 'NAICS', 172, 213, 2, 175, 213111, 5),
(6795, 'SIC', 2939, 1500, 2, 2946, 1541, 4),
(6796, 'SIC', 3576, 3900, 2, 3598, 3995, 4),
(6797, 'NAICS', 2037, 81, 1, 2067, 811430, 5),
(6798, 'SEC', 2277, 2420, 3, 2278, 2421, 4),
(6799, 'SIC', 3419, 3500, 2, 3431, 3535, 4),
(6800, 'SIC', 4309, 40, 1, 3704, 4939, 4),
(6801, 'SIC', 3917, 6000, 2, 3921, 6020, 3),
(6802, 'SEC', 2791, 20, 1, 2277, 2420, 3),
(6803, 'SEC', 2659, 6100, 2, 4323, 6189, 4),
(6804, 'SIC', 3115, 2390, 3, 3123, 2399, 4),
(6805, 'SEC', 2384, 3400, 2, 2386, 3411, 4),
(6806, 'SEC', 2791, 20, 1, 2498, 3870, 3),
(6807, 'SIC', 4313, 70, 1, 4181, 8220, 3),
(6808, 'NAICS', 1577, 53113, 4, 1576, 531130, 5),
(6809, 'SIC', 4040, 7300, 2, 4052, 7335, 4),
(6810, 'NAICS', 1506, 5223, 3, 1509, 522320, 5),
(6811, 'NAICS', 2189, 9261, 3, 2198, 926150, 5),
(6812, 'NAICS', 1592, 5321, 3, 1597, 53212, 4),
(6813, 'NAICS', 1624, 54, 1, 1641, 541310, 5),
(6814, 'NAICS', 2071, 812, 2, 2083, 812220, 5),
(6815, 'SIC', 3526, 3700, 2, 3530, 3714, 4),
(6816, 'NAICS', 1570, 531, 2, 1581, 531210, 5),
(6817, 'SIC', 3190, 2700, 2, 3208, 2780, 3),
(6818, 'NAICS', 1485, 522, 2, 1506, 5223, 3),
(6819, 'SIC', 4305, 1, 1, 2813, 170, 3),
(6820, 'NAICS', 207, 2361, 3, 209, 236115, 5),
(6821, 'SEC', 2691, 6400, 2, 2693, 6411, 4),
(6822, 'SEC', 2458, 3700, 2, 2466, 3721, 4),
(6823, 'NAICS', 930, 42, 1, 1050, 424480, 5),
(6824, 'SEC', 2790, 15, 1, 2234, 1600, 2),
(6825, 'SIC', 3149, 2510, 3, 3153, 2515, 4),
(6826, 'SIC', 4308, 20, 1, 3151, 2512, 4),
(6827, 'SEC', 2788, 1, 1, 2210, 100, 2),
(6828, 'NAICS', 1625, 541, 2, 1702, 541870, 5),
(6829, 'SIC', 4312, 60, 1, 3957, 6289, 4),
(6830, 'SIC', 3948, 6200, 2, 3954, 6231, 4),
(6831, 'SIC', 4308, 20, 1, 3119, 2394, 4),
(6832, 'SIC', 4310, 50, 1, 3772, 5137, 4),
(6833, 'SIC', 4308, 20, 1, 2985, 2013, 4),
(6834, 'SIC', 4308, 20, 1, 3580, 3915, 4),
(6835, 'SIC', 3811, 5260, 3, 3812, 5261, 4),
(6836, 'NAICS', 1, 11, 1, 28, 11133, 4),
(6837, 'SIC', 4308, 20, 1, 3212, 2791, 4),
(6838, 'SIC', 3978, 6510, 3, 3982, 6515, 4),
(6839, 'NAICS', 205, 23, 1, 263, 238320, 5),
(6840, 'NAICS', 1624, 54, 1, 1714, 541940, 5),
(6841, 'SEC', 2791, 20, 1, 2424, 3570, 3),
(6842, 'SIC', 3468, 3580, 3, 3469, 3581, 4),
(6843, 'SEC', 2215, 1000, 2, 2216, 1040, 3),
(6844, 'SEC', 2403, 3500, 2, 2426, 3572, 4),
(6845, 'SIC', 4259, 9220, 3, 4263, 9224, 4),
(6846, 'NAICS', 930, 42, 1, 1002, 423860, 5),
(6847, 'NAICS', 2157, 92213, 4, 2156, 922130, 5),
(6848, 'SEC', 2371, 3300, 2, 2378, 3340, 3),
(6849, 'NAICS', 1634, 5412, 3, 1639, 541219, 5),
(6850, 'NAICS', 205, 23, 1, 257, 23822, 4),
(6851, 'NAICS', 1442, 515, 2, 1448, 51512, 4),
(6852, 'SIC', 3371, 3400, 2, 3382, 3432, 4),
(6853, 'SIC', 4041, 7310, 3, 4045, 7319, 4),
(6854, 'NAICS', 260, 2383, 3, 261, 238310, 5),
(6855, 'SIC', 4308, 20, 1, 3462, 3571, 4),
(6856, 'NAICS', 132, 21, 1, 139, 2121, 3),
(6857, 'NAICS', 1470, 519, 2, 1473, 51911, 4),
(6858, 'NAICS', 1402, 51, 1, 1454, 517110, 5),
(6859, 'SEC', 2692, 6410, 3, 2693, 6411, 4),
(6860, 'NAICS', 1591, 532, 2, 1614, 532411, 5),
(6861, 'SEC', 2790, 15, 1, 2231, 1530, 3),
(6862, 'SIC', 4305, 1, 1, 2814, 171, 4),
(6863, 'SEC', 2670, 6200, 2, 2673, 6220, 3),
(6864, 'NAICS', 1, 11, 1, 43, 1119, 3),
(6865, 'NAICS', 1090, 4251, 3, 1094, 42512, 4),
(6866, 'NAICS', 1721, 55111, 4, 1724, 551114, 5),
(6867, 'SIC', 2955, 1700, 2, 2964, 1742, 4),
(6868, 'NAICS', 2052, 8112, 3, 2053, 81121, 4),
(6869, 'NAICS', 1726, 561, 2, 1741, 5614, 3),
(6870, 'NAICS', 70, 11231, 4, 69, 112310, 5),
(6871, 'SIC', 4311, 52, 1, 3851, 5571, 4),
(6872, 'NAICS', 235, 238, 2, 262, 23831, 4),
(6873, 'NAICS', 1979, 713, 2, 1987, 71321, 4),
(6874, 'NAICS', 1851, 621, 2, 1852, 6211, 3),
(6875, 'NAICS', 2, 111, 2, 22, 111219, 5),
(6876, 'SIC', 4308, 20, 1, 2994, 2032, 4),
(6877, 'NAICS', 1569, 53, 1, 1613, 53241, 4),
(6878, 'SIC', 4311, 52, 1, 3828, 5431, 4),
(6879, 'SIC', 3655, 4510, 3, 3656, 4512, 4),
(6880, 'NAICS', 1015, 424, 2, 1055, 424510, 5),
(6881, 'NAICS', 1900, 62221, 4, 1899, 622210, 5),
(6882, 'NAICS', 1725, 56, 1, 1780, 56173, 4),
(6883, 'SIC', 4314, 90, 1, 4283, 9532, 4),
(6884, 'NAICS', 946, 4233, 3, 951, 423330, 5),
(6885, 'NAICS', 1726, 561, 2, 1789, 56192, 4),
(6886, 'SIC', 4308, 20, 1, 3183, 2673, 4),
(6887, 'SIC', 3977, 6500, 2, 3991, 6553, 4),
(6888, 'SIC', 4284, 9600, 2, 4288, 9621, 4),
(6889, 'NAICS', 1942, 71, 1, 1953, 7112, 3),
(6890, 'NAICS', 36, 1114, 3, 42, 111422, 5),
(6891, 'NAICS', 1689, 5418, 3, 1701, 54186, 4),
(6892, 'SIC', 4313, 70, 1, 4060, 7353, 4),
(6893, 'NAICS', 930, 42, 1, 933, 423110, 5),
(6894, 'SEC', 2355, 3200, 2, 2365, 3260, 3),
(6895, 'NAICS', 1479, 51919, 4, 1478, 519190, 5),
(6896, 'NAICS', 225, 23713, 4, 224, 237130, 5),
(6897, 'NAICS', 1812, 61, 1, 1818, 611210, 5),
(6898, 'NAICS', 955, 4234, 3, 956, 423410, 5),
(6899, 'NAICS', 930, 42, 1, 1025, 42421, 4),
(6900, 'SIC', 3419, 3500, 2, 3444, 3550, 3),
(6901, 'NAICS', 1624, 54, 1, 1636, 541211, 5),
(6902, 'SIC', 2987, 2020, 3, 2991, 2024, 4),
(6903, 'NAICS', 1530, 52392, 4, 1529, 523920, 5),
(6904, 'SIC', 3484, 3620, 3, 3487, 3625, 4),
(6905, 'NAICS', 28, 11133, 4, 35, 111339, 5),
(6906, 'SIC', 3190, 2700, 2, 3198, 2740, 3),
(6907, 'SIC', 3083, 2300, 2, 3100, 2342, 4),
(6908, 'NAICS', 132, 21, 1, 135, 21111, 4),
(6909, 'SEC', 2791, 20, 1, 2474, 3760, 3),
(6910, 'SIC', 3693, 4900, 2, 3712, 4961, 4),
(6911, 'SEC', 2470, 3740, 3, 2471, 3743, 4),
(6912, 'SIC', 3620, 4200, 2, 3624, 4214, 4),
(6913, 'NAICS', 72, 11232, 4, 71, 112320, 5),
(6914, 'SIC', 3050, 2200, 2, 3057, 2240, 3),
(6915, 'NAICS', 1467, 5182, 3, 1469, 51821, 4),
(6916, 'SIC', 2982, 2000, 2, 3019, 2068, 4),
(6917, 'SIC', 4312, 60, 1, 3960, 6311, 4),
(6918, 'NAICS', 2163, 92216, 4, 2162, 922160, 5),
(6919, 'NAICS', 1452, 517, 2, 1464, 517911, 5),
(6920, 'SEC', 2643, 5940, 3, 2645, 5945, 4),
(6921, 'SIC', 4308, 20, 1, 3175, 2652, 4),
(6922, 'NAICS', 1571, 5311, 3, 1572, 531110, 5),
(6923, 'SIC', 4313, 70, 1, 4038, 7291, 4),
(6924, 'SIC', 2847, 700, 2, 2858, 750, 3),
(6925, 'SIC', 3337, 3300, 2, 3338, 3310, 3),
(6926, 'NAICS', 1624, 54, 1, 1668, 541511, 5),
(6927, 'NAICS', 2135, 92, 1, 2173, 92313, 4),
(6928, 'NAICS', 1881, 6215, 3, 1882, 62151, 4),
(6929, 'NAICS', 1943, 711, 2, 1954, 71121, 4),
(6930, 'SIC', 3214, 2800, 2, 3241, 2870, 3),
(6931, 'SEC', 2371, 3300, 2, 2374, 3317, 4),
(6932, 'NAICS', 205, 23, 1, 242, 23813, 4),
(6933, 'NAICS', 37, 11141, 4, 38, 111411, 5),
(6934, 'SIC', 3159, 2530, 3, 3160, 2531, 4),
(6935, 'SIC', 3050, 2200, 2, 3069, 2262, 4),
(6936, 'SIC', 3526, 3700, 2, 3535, 3724, 4),
(6937, 'NAICS', 1, 11, 1, 7, 11112, 4),
(6938, 'NAICS', 931, 423, 2, 972, 42351, 4),
(6939, 'SIC', 3404, 3480, 3, 3405, 3482, 4),
(6940, 'SEC', 2649, 6000, 2, 2658, 6099, 4),
(6941, 'NAICS', 1570, 531, 2, 1589, 531390, 5),
(6942, 'NAICS', 1054, 4245, 3, 1059, 424590, 5),
(6943, 'SIC', 4313, 70, 1, 4015, 7040, 3),
(6944, 'NAICS', 1035, 4244, 3, 1037, 42441, 4),
(6945, 'NAICS', 1480, 52, 1, 1560, 525190, 5),
(6946, 'SIC', 3419, 3500, 2, 3453, 3562, 4),
(6947, 'NAICS', 1719, 551, 2, 1723, 551112, 5),
(6948, 'SIC', 3958, 6300, 2, 3959, 6310, 3),
(6949, 'NAICS', 1942, 71, 1, 1975, 712130, 5),
(6950, 'SIC', 3316, 3260, 3, 3317, 3261, 4),
(6951, 'NAICS', 1819, 61121, 4, 1818, 611210, 5),
(6952, 'SIC', 2982, 2000, 2, 3031, 2086, 4),
(6953, 'NAICS', 2120, 8139, 3, 2123, 813920, 5),
(6954, 'NAICS', 1942, 71, 1, 1968, 71151, 4),
(6955, 'SIC', 3662, 4600, 2, 3666, 4619, 4),
(6956, 'SIC', 4313, 70, 1, 4209, 8610, 3),
(6957, 'NAICS', 2131, 814, 2, 2132, 8141, 3),
(6958, 'SIC', 4308, 20, 1, 3591, 3955, 4),
(6959, 'NAICS', 1425, 51213, 4, 1427, 512132, 5),
(6960, 'SEC', 2396, 3450, 3, 2398, 3452, 4),
(6961, 'NAICS', 260, 2383, 3, 270, 23835, 4),
(6962, 'NAICS', 1420, 5121, 3, 1426, 512131, 5),
(6963, 'SIC', 4313, 70, 1, 4214, 8631, 4),
(6964, 'SEC', 2302, 2700, 2, 2303, 2710, 3),
(6965, 'SIC', 4313, 70, 1, 4142, 7993, 4),
(6966, 'SIC', 3474, 3590, 3, 3477, 3594, 4),
(6967, 'SIC', 3371, 3400, 2, 3409, 3490, 3),
(6968, 'NAICS', 969, 42349, 4, 968, 423490, 5),
(6969, 'NAICS', 1403, 511, 2, 1407, 511120, 5),
(6970, 'NAICS', 1941, 62441, 4, 1940, 624410, 5),
(6971, 'SEC', 2791, 20, 1, 2296, 2621, 4),
(6972, 'SIC', 4308, 20, 1, 3198, 2740, 3),
(6973, 'SIC', 3620, 4200, 2, 3630, 4226, 4),
(6974, 'SIC', 4311, 52, 1, 3871, 5712, 4),
(6975, 'SEC', 2229, 1500, 2, 2230, 1520, 3),
(6976, 'SIC', 3230, 2840, 3, 3233, 2843, 4),
(6977, 'NAICS', 1026, 4243, 3, 1029, 424320, 5),
(6978, 'NAICS', 1888, 6219, 3, 1889, 621910, 5),
(6979, 'SIC', 4309, 40, 1, 3663, 4610, 3),
(6980, 'NAICS', 1485, 522, 2, 1512, 52239, 4),
(6981, 'NAICS', 1624, 54, 1, 1679, 541620, 5),
(6982, 'SIC', 4062, 7360, 3, 4064, 7363, 4),
(6983, 'NAICS', 52, 11199, 4, 55, 111998, 5),
(6984, 'SIC', 4308, 20, 1, 3256, 2951, 4),
(6985, 'NAICS', 1485, 522, 2, 1490, 52212, 4),
(6986, 'NAICS', 1713, 54193, 4, 1712, 541930, 5),
(6987, 'NAICS', 1, 11, 1, 90, 112910, 5),
(6988, 'NAICS', 1733, 5613, 3, 1740, 56133, 4),
(6989, 'SEC', 2796, 70, 1, 2776, 8711, 4),
(6990, 'SIC', 3246, 2890, 3, 3249, 2893, 4),
(6991, 'SIC', 3886, 5900, 2, 3894, 5941, 4),
(6992, 'NAICS', 157, 21231, 4, 158, 212311, 5),
(6993, 'SIC', 4313, 70, 1, 4018, 7210, 3),
(6994, 'NAICS', 1076, 4249, 3, 1084, 42494, 4),
(6995, 'SIC', 4308, 20, 1, 3474, 3590, 3),
(6996, 'NAICS', 1850, 62, 1, 1856, 6212, 3),
(6997, 'NAICS', 2147, 92115, 4, 2146, 921150, 5),
(6998, 'SIC', 3137, 2440, 3, 3138, 2441, 4),
(6999, 'NAICS', 1, 11, 1, 42, 111422, 5),
(7000, 'NAICS', 206, 236, 2, 216, 236220, 5),
(7001, 'NAICS', 1625, 541, 2, 1706, 5419, 3),
(7002, 'SIC', 4308, 20, 1, 3539, 3732, 4),
(7003, 'SIC', 3533, 3720, 3, 3534, 3721, 4),
(7004, 'NAICS', 181, 221, 2, 189, 221116, 5),
(7005, 'NAICS', 1, 11, 1, 59, 112111, 5),
(7006, 'NAICS', 2061, 8114, 3, 2064, 811412, 5),
(7007, 'NAICS', 2085, 8123, 3, 2091, 812331, 5),
(7008, 'NAICS', 2103, 813, 2, 2117, 8134, 3),
(7009, 'SEC', 2677, 6300, 2, 2690, 6399, 4),
(7010, 'SIC', 3190, 2700, 2, 3211, 2790, 3),
(7011, 'SEC', 2788, 1, 1, 2211, 200, 2),
(7012, 'NAICS', 138, 212, 2, 163, 212321, 5),
(7013, 'NAICS', 1784, 56179, 4, 1783, 561790, 5),
(7014, 'NAICS', 1851, 621, 2, 1855, 621112, 5),
(7015, 'SIC', 4293, 9650, 3, 4294, 9651, 4),
(7016, 'SIC', 4308, 20, 1, 3040, 2099, 4),
(7017, 'NAICS', 253, 2382, 3, 259, 23829, 4),
(7018, 'NAICS', 1625, 541, 2, 1701, 54186, 4),
(7019, 'NAICS', 56, 112, 2, 83, 11242, 4),
(7020, 'SIC', 4311, 52, 1, 3805, 5210, 3),
(7021, 'NAICS', 1, 11, 1, 69, 112310, 5),
(7022, 'NAICS', 138, 212, 2, 145, 212210, 5),
(7023, 'NAICS', 2200, 927, 2, 2202, 927110, 5),
(7024, 'SEC', 2794, 52, 1, 2607, 5211, 4),
(7025, 'SIC', 3215, 2810, 3, 3219, 2819, 4),
(7026, 'SIC', 4313, 70, 1, 4036, 7261, 4),
(7027, 'SIC', 3012, 2060, 3, 3015, 2063, 4),
(7028, 'NAICS', 1015, 424, 2, 1034, 42434, 4),
(7029, 'SIC', 4308, 20, 1, 3334, 3296, 4),
(7030, 'SIC', 4309, 40, 1, 3673, 4731, 4),
(7031, 'SEC', 2791, 20, 1, 2392, 3442, 4),
(7032, 'SIC', 4314, 90, 1, 4304, 9999, 4),
(7033, 'NAICS', 931, 423, 2, 968, 423490, 5),
(7034, 'NAICS', 1485, 522, 2, 1495, 5222, 3),
(7035, 'SIC', 3287, 3140, 3, 3291, 3149, 4),
(7036, 'SIC', 3693, 4900, 2, 3711, 4960, 3),
(7037, 'NAICS', 2038, 811, 2, 2046, 811121, 5),
(7038, 'SIC', 4309, 40, 1, 3653, 4499, 4),
(7039, 'NAICS', 1635, 54121, 4, 1639, 541219, 5),
(7040, 'NAICS', 1569, 53, 1, 1621, 5331, 3),
(7041, 'SIC', 4109, 7690, 3, 4112, 7699, 4),
(7042, 'SEC', 2623, 5600, 2, 2628, 5660, 3),
(7043, 'NAICS', 1404, 5111, 3, 1406, 51111, 4),
(7044, 'SIC', 4308, 20, 1, 3578, 3911, 4),
(7045, 'NAICS', 205, 23, 1, 225, 23713, 4),
(7046, 'SIC', 3170, 2620, 3, 3171, 2621, 4),
(7047, 'SEC', 2555, 4920, 3, 2557, 4923, 4),
(7048, 'SIC', 3144, 2490, 3, 3147, 2499, 4),
(7049, 'SIC', 4313, 70, 1, 4047, 7322, 4),
(7050, 'NAICS', 1480, 52, 1, 1483, 521110, 5),
(7051, 'NAICS', 2068, 81143, 4, 2067, 811430, 5),
(7052, 'NAICS', 1466, 518, 2, 1467, 5182, 3),
(7053, 'SIC', 3620, 4200, 2, 3631, 4230, 3),
(7054, 'SIC', 3282, 3100, 2, 3299, 3190, 3),
(7055, 'SIC', 3362, 3360, 3, 3364, 3364, 4),
(7056, 'NAICS', 1514, 5231, 3, 1517, 523120, 5),
(7057, 'SIC', 4310, 50, 1, 3742, 5064, 4),
(7058, 'SIC', 4312, 60, 1, 3987, 6540, 3),
(7059, 'NAICS', 2020, 722, 2, 2022, 722310, 5),
(7060, 'SEC', 2577, 5050, 3, 2578, 5051, 4),
(7061, 'SIC', 4235, 8740, 3, 4238, 8743, 4),
(7062, 'NAICS', 2037, 81, 1, 2064, 811412, 5),
(7063, 'NAICS', 144, 2122, 3, 146, 21221, 4),
(7064, 'SIC', 4306, 10, 1, 2897, 1081, 4),
(7065, 'SIC', 4033, 7250, 3, 4034, 7251, 4),
(7066, 'SIC', 4306, 10, 1, 2891, 1040, 3),
(7067, 'NAICS', 1979, 713, 2, 1984, 71312, 4),
(7068, 'SIC', 3992, 6700, 2, 4001, 6733, 4),
(7069, 'SEC', 2791, 20, 1, 2259, 2100, 2),
(7070, 'SIC', 4312, 60, 1, 3954, 6231, 4),
(7071, 'SIC', 3948, 6200, 2, 3957, 6289, 4),
(7072, 'NAICS', 1624, 54, 1, 1697, 54184, 4),
(7073, 'SEC', 2476, 3800, 2, 2496, 3860, 3),
(7074, 'SIC', 4046, 7320, 3, 4047, 7322, 4),
(7075, 'SEC', 2793, 50, 1, 2580, 5063, 4),
(7076, 'NAICS', 1, 11, 1, 50, 111940, 5),
(7077, 'NAICS', 1570, 531, 2, 1585, 531311, 5),
(7078, 'NAICS', 930, 42, 1, 1077, 424910, 5),
(7079, 'SIC', 4310, 50, 1, 3717, 5012, 4),
(7080, 'NAICS', 1590, 53139, 4, 1589, 531390, 5),
(7081, 'SIC', 4308, 20, 1, 3585, 3944, 4),
(7082, 'NAICS', 2020, 722, 2, 2028, 7224, 3),
(7083, 'SIC', 4313, 70, 1, 4196, 8331, 4),
(7084, 'NAICS', 1850, 62, 1, 1938, 62431, 4),
(7085, 'SIC', 4307, 15, 1, 2950, 1611, 4),
(7086, 'SIC', 4040, 7300, 2, 4049, 7330, 3),
(7087, 'NAICS', 1, 11, 1, 118, 1151, 3),
(7088, 'NAICS', 172, 213, 2, 176, 213112, 5),
(7089, 'SEC', 2709, 7000, 2, 2710, 7010, 3),
(7090, 'SIC', 3716, 5010, 3, 3718, 5013, 4),
(7091, 'SIC', 4256, 9200, 2, 4257, 9210, 3),
(7092, 'SIC', 4308, 20, 1, 3460, 3569, 4),
(7093, 'SEC', 2794, 52, 1, 2616, 5399, 4),
(7094, 'SIC', 4305, 1, 1, 2802, 115, 4),
(7095, 'SIC', 3877, 5730, 3, 3881, 5736, 4),
(7096, 'NAICS', 1812, 61, 1, 1845, 611692, 5),
(7097, 'NAICS', 2093, 8129, 3, 2101, 812990, 5),
(7098, 'SEC', 2792, 40, 1, 2558, 4924, 4),
(7099, 'SEC', 2753, 8000, 2, 2759, 8062, 4),
(7100, 'SIC', 3618, 4170, 3, 3619, 4173, 4),
(7101, 'SIC', 3955, 6280, 3, 3957, 6289, 4),
(7102, 'SEC', 2349, 3080, 3, 2352, 3089, 4),
(7103, 'NAICS', 930, 42, 1, 944, 423220, 5),
(7104, 'NAICS', 1624, 54, 1, 1631, 54119, 4),
(7105, 'NAICS', 1792, 562, 2, 1800, 562211, 5),
(7106, 'SIC', 3083, 2300, 2, 3111, 2385, 4),
(7107, 'NAICS', 205, 23, 1, 236, 2381, 3),
(7108, 'SIC', 2847, 700, 2, 2859, 751, 4),
(7109, 'NAICS', 930, 42, 1, 1036, 424410, 5),
(7110, 'SIC', 4314, 90, 1, 4290, 9631, 4),
(7111, 'SEC', 2791, 20, 1, 2248, 2033, 4),
(7112, 'SIC', 4308, 20, 1, 3461, 3570, 3),
(7113, 'SIC', 4312, 60, 1, 3936, 6099, 4),
(7114, 'NAICS', 1480, 52, 1, 1565, 525920, 5),
(7115, 'SIC', 3737, 5050, 3, 3738, 5051, 4),
(7116, 'SIC', 4308, 20, 1, 3214, 2800, 2),
(7117, 'SIC', 3649, 4490, 3, 3651, 4492, 4),
(7118, 'NAICS', 1402, 51, 1, 1467, 5182, 3),
(7119, 'SEC', 2670, 6200, 2, 2671, 6210, 3),
(7120, 'NAICS', 1640, 5413, 3, 1643, 541320, 5),
(7121, 'NAICS', 931, 423, 2, 973, 423520, 5),
(7122, 'NAICS', 2020, 722, 2, 2023, 72231, 4),
(7123, 'SIC', 4308, 20, 1, 3211, 2790, 3),
(7124, 'SIC', 4311, 52, 1, 3895, 5942, 4),
(7125, 'NAICS', 1868, 62139, 4, 1869, 621391, 5),
(7126, 'SEC', 2713, 7300, 2, 2722, 7360, 3),
(7127, 'SIC', 4314, 90, 1, 4279, 9511, 4),
(7128, 'SIC', 4312, 60, 1, 3935, 6091, 4),
(7129, 'SIC', 4162, 8060, 3, 4163, 8062, 4),
(7130, 'SIC', 4192, 8300, 2, 4201, 8390, 3),
(7131, 'SIC', 2798, 100, 2, 2810, 139, 4),
(7132, 'NAICS', 1404, 5111, 3, 1413, 51119, 4),
(7133, 'NAICS', 1569, 53, 1, 1606, 532291, 5),
(7134, 'SIC', 2847, 700, 2, 2863, 762, 4),
(7135, 'SEC', 2331, 2850, 3, 2332, 2851, 4),
(7136, 'SIC', 2955, 1700, 2, 2969, 1760, 3),
(7137, 'SEC', 2591, 5100, 2, 2594, 5122, 4),
(7138, 'SIC', 4120, 7830, 3, 4121, 7832, 4),
(7139, 'SIC', 3124, 2400, 2, 3134, 2435, 4),
(7140, 'NAICS', 1850, 62, 1, 1866, 621340, 5),
(7141, 'NAICS', 2048, 81119, 4, 2049, 811191, 5),
(7142, 'SEC', 2536, 4700, 2, 2538, 4731, 4),
(7143, 'SEC', 2568, 5000, 2, 2589, 5094, 4),
(7144, 'NAICS', 1413, 51119, 4, 1414, 511191, 5),
(7145, 'NAICS', 1942, 71, 1, 1974, 71212, 4),
(7146, 'SIC', 4314, 90, 1, 4270, 9411, 4),
(7147, 'NAICS', 930, 42, 1, 934, 42311, 4),
(7148, 'SIC', 3804, 5200, 2, 3813, 5270, 3),
(7149, 'NAICS', 993, 42381, 4, 992, 423810, 5),
(7150, 'SIC', 3115, 2390, 3, 3116, 2391, 4),
(7151, 'SIC', 4241, 8800, 2, 4242, 8810, 3),
(7152, 'NAICS', 930, 42, 1, 1020, 42412, 4),
(7153, 'SIC', 3724, 5030, 3, 3727, 5033, 4),
(7154, 'NAICS', 1758, 5615, 3, 1765, 561599, 5),
(7155, 'SIC', 4308, 20, 1, 3597, 3993, 4),
(7156, 'SIC', 3636, 4400, 2, 3644, 4449, 4),
(7157, 'NAICS', 1666, 5415, 3, 1670, 541513, 5),
(7158, 'SIC', 4307, 15, 1, 2956, 1710, 3),
(7159, 'SIC', 3804, 5200, 2, 3807, 5230, 3),
(7160, 'SIC', 3371, 3400, 2, 3375, 3420, 3),
(7161, 'NAICS', 182, 2211, 3, 183, 22111, 4),
(7162, 'NAICS', 1554, 525, 2, 1564, 52591, 4),
(7163, 'SEC', 2795, 60, 1, 2677, 6300, 2),
(7164, 'SIC', 4314, 90, 1, 4280, 9512, 4),
(7165, 'SEC', 2795, 60, 1, 2672, 6211, 4),
(7166, 'SIC', 2983, 2010, 3, 2984, 2011, 4),
(7167, 'SIC', 4305, 1, 1, 2856, 741, 4),
(7168, 'NAICS', 1015, 424, 2, 1050, 424480, 5),
(7169, 'NAICS', 1942, 71, 1, 1962, 71132, 4),
(7170, 'SIC', 3977, 6500, 2, 3978, 6510, 3),
(7171, 'SEC', 2617, 5400, 2, 2618, 5410, 3),
(7172, 'SIC', 4049, 7330, 3, 4050, 7331, 4),
(7173, 'SEC', 2670, 6200, 2, 2672, 6211, 4),
(7174, 'NAICS', 2038, 811, 2, 2067, 811430, 5),
(7175, 'SEC', 2240, 2000, 2, 2253, 2070, 3),
(7176, 'NAICS', 2032, 72251, 4, 2035, 722514, 5),
(7177, 'SEC', 2539, 4800, 2, 2542, 4813, 4),
(7178, 'SIC', 4308, 20, 1, 3551, 3799, 4),
(7179, 'SIC', 4029, 7230, 3, 4030, 7231, 4),
(7180, 'SIC', 4281, 9530, 3, 4282, 9531, 4),
(7181, 'NAICS', 138, 212, 2, 151, 212231, 5),
(7182, 'NAICS', 2166, 923, 2, 2168, 923110, 5),
(7183, 'SEC', 2791, 20, 1, 2276, 2400, 2),
(7184, 'NAICS', 1485, 522, 2, 1491, 522130, 5),
(7185, 'NAICS', 1928, 6242, 3, 1935, 62423, 4),
(7186, 'SIC', 3426, 3530, 3, 3428, 3532, 4),
(7187, 'SIC', 4297, 9700, 2, 4299, 9711, 4),
(7188, 'NAICS', 1403, 511, 2, 1417, 511210, 5),
(7189, 'SIC', 4309, 40, 1, 3707, 4950, 3),
(7190, 'SEC', 2713, 7300, 2, 2733, 7384, 4),
(7191, 'SIC', 4308, 20, 1, 3284, 3111, 4),
(7192, 'NAICS', 1570, 531, 2, 1586, 531312, 5),
(7193, 'NAICS', 1726, 561, 2, 1740, 56133, 4),
(7194, 'NAICS', 1942, 71, 1, 1988, 713290, 5),
(7195, 'SEC', 2626, 5650, 3, 2627, 5651, 4),
(7196, 'SIC', 4089, 7530, 3, 4092, 7534, 4),
(7197, 'SIC', 4310, 50, 1, 3757, 5091, 4),
(7198, 'SIC', 4224, 8710, 3, 4225, 8711, 4),
(7199, 'NAICS', 1495, 5222, 3, 1504, 522294, 5),
(7200, 'NAICS', 1513, 523, 2, 1528, 52391, 4),
(7201, 'SEC', 2796, 70, 1, 2745, 7830, 3),
(7202, 'SIC', 3296, 3170, 3, 3298, 3172, 4),
(7203, 'SEC', 2795, 60, 1, 2671, 6210, 3),
(7204, 'SIC', 4308, 20, 1, 3321, 3269, 4),
(7205, 'SEC', 2500, 3900, 2, 2506, 3942, 4),
(7206, 'NAICS', 1689, 5418, 3, 1692, 541820, 5),
(7207, 'SEC', 2738, 7800, 2, 2739, 7810, 3),
(7208, 'NAICS', 1402, 51, 1, 1443, 5151, 3),
(7209, 'NAICS', 1420, 5121, 3, 1423, 512120, 5),
(7210, 'SIC', 4312, 60, 1, 4003, 6792, 4),
(7211, 'SIC', 4308, 20, 1, 2996, 2034, 4),
(7212, 'NAICS', 1859, 6213, 3, 1860, 621310, 5),
(7213, 'NAICS', 930, 42, 1, 1015, 424, 2),
(7214, 'NAICS', 1612, 5324, 3, 1619, 53249, 4),
(7215, 'SIC', 4308, 20, 1, 3325, 3273, 4),
(7216, 'NAICS', 1625, 541, 2, 1699, 54185, 4),
(7217, 'NAICS', 1942, 71, 1, 2001, 713990, 5),
(7218, 'SIC', 4314, 90, 1, 4298, 9710, 3),
(7219, 'NAICS', 1547, 5242, 3, 1552, 524292, 5),
(7220, 'NAICS', 2182, 925, 2, 2183, 9251, 3),
(7221, 'NAICS', 98, 113, 2, 99, 1131, 3),
(7222, 'NAICS', 930, 42, 1, 960, 423430, 5),
(7223, 'SIC', 4305, 1, 1, 2823, 190, 3),
(7224, 'NAICS', 1536, 524, 2, 1547, 5242, 3),
(7225, 'NAICS', 1859, 6213, 3, 1862, 621320, 5),
(7226, 'SIC', 4307, 15, 1, 2977, 1793, 4),
(7227, 'SIC', 2982, 2000, 2, 2997, 2035, 4),
(7228, 'SIC', 3837, 5500, 2, 3852, 5590, 3),
(7229, 'NAICS', 1402, 51, 1, 1422, 51211, 4),
(7230, 'SEC', 2793, 50, 1, 2571, 5020, 3),
(7231, 'SIC', 4308, 20, 1, 3348, 3325, 4),
(7232, 'SIC', 3769, 5130, 3, 3770, 5131, 4),
(7233, 'NAICS', 2167, 9231, 3, 2174, 923140, 5),
(7234, 'SIC', 4308, 20, 1, 3504, 3650, 3),
(7235, 'NAICS', 930, 42, 1, 950, 42332, 4),
(7236, 'SIC', 3371, 3400, 2, 3394, 3452, 4),
(7237, 'NAICS', 1942, 71, 1, 1943, 711, 2),
(7238, 'SIC', 4311, 52, 1, 3858, 5621, 4),
(7239, 'NAICS', 2003, 72, 1, 2005, 7211, 3),
(7240, 'SIC', 4305, 1, 1, 2868, 800, 2),
(7241, 'SIC', 3555, 3820, 3, 3558, 3823, 4),
(7242, 'NAICS', 132, 21, 1, 172, 213, 2),
(7243, 'NAICS', 1812, 61, 1, 1819, 61121, 4),
(7244, 'NAICS', 1, 11, 1, 36, 1114, 3),
(7245, 'NAICS', 259, 23829, 4, 258, 238290, 5),
(7246, 'SIC', 4308, 20, 1, 3425, 3524, 4),
(7247, 'NAICS', 1403, 511, 2, 1408, 51112, 4),
(7248, 'SEC', 2791, 20, 1, 2510, 3960, 3),
(7249, 'NAICS', 1827, 61142, 4, 1826, 611420, 5),
(7250, 'NAICS', 2039, 8111, 3, 2045, 81112, 4),
(7251, 'SEC', 2791, 20, 1, 2491, 3843, 4),
(7252, 'SIC', 3208, 2780, 3, 3210, 2789, 4),
(7253, 'NAICS', 1943, 711, 2, 1946, 71111, 4),
(7254, 'SEC', 2791, 20, 1, 2301, 2673, 4),
(7255, 'SIC', 4308, 20, 1, 3276, 3084, 4),
(7256, 'SIC', 3480, 3600, 2, 3513, 3672, 4),
(7257, 'NAICS', 1812, 61, 1, 1841, 611630, 5),
(7258, 'NAICS', 1721, 55111, 4, 1722, 551111, 5),
(7259, 'SIC', 3093, 2330, 3, 3095, 2335, 4),
(7260, 'NAICS', 1015, 424, 2, 1054, 4245, 3),
(7261, 'NAICS', 1403, 511, 2, 1416, 5112, 3),
(7262, 'NAICS', 1697, 54184, 4, 1696, 541840, 5),
(7263, 'NAICS', 2061, 8114, 3, 2063, 811411, 5),
(7264, 'SIC', 4089, 7530, 3, 4093, 7536, 4),
(7265, 'NAICS', 1459, 5174, 3, 1460, 517410, 5),
(7266, 'SEC', 2794, 52, 1, 2615, 5390, 3),
(7267, 'SIC', 4308, 20, 1, 3399, 3466, 4),
(7268, 'SIC', 3883, 5810, 3, 3885, 5813, 4),
(7269, 'NAICS', 2135, 92, 1, 2157, 92213, 4),
(7270, 'NAICS', 236, 2381, 3, 249, 238170, 5),
(7271, 'NAICS', 132, 21, 1, 133, 211, 2),
(7272, 'SIC', 3084, 2310, 3, 3085, 2311, 4),
(7273, 'NAICS', 1034, 42434, 4, 1033, 424340, 5),
(7274, 'NAICS', 1726, 561, 2, 1779, 561730, 5),
(7275, 'NAICS', 1873, 62141, 4, 1872, 621410, 5),
(7276, 'SIC', 4308, 20, 1, 3357, 3353, 4),
(7277, 'NAICS', 1851, 621, 2, 1867, 62134, 4),
(7278, 'SIC', 4146, 8000, 2, 4169, 8080, 3),
(7279, 'SIC', 3148, 2500, 2, 3166, 2599, 4),
(7280, 'NAICS', 1480, 52, 1, 1520, 52313, 4),
(7281, 'SIC', 4308, 20, 1, 3365, 3365, 4),
(7282, 'SIC', 3282, 3100, 2, 3296, 3170, 3),
(7283, 'NAICS', 1859, 6213, 3, 1869, 621391, 5),
(7284, 'SIC', 4306, 10, 1, 2899, 1094, 4),
(7285, 'SIC', 4308, 20, 1, 3476, 3593, 4),
(7286, 'SIC', 4314, 90, 1, 4259, 9220, 3),
(7287, 'NAICS', 1792, 562, 2, 1809, 56299, 4),
(7288, 'NAICS', 156, 2123, 3, 163, 212321, 5),
(7289, 'SIC', 4308, 20, 1, 2984, 2011, 4),
(7290, 'SEC', 2792, 40, 1, 2519, 4213, 4),
(7291, 'NAICS', 1625, 541, 2, 1707, 541910, 5),
(7292, 'SIC', 3533, 3720, 3, 3536, 3728, 4),
(7293, 'SIC', 4208, 8600, 2, 4212, 8621, 4),
(7294, 'NAICS', 235, 238, 2, 273, 2389, 3),
(7295, 'NAICS', 1625, 541, 2, 1630, 54112, 4),
(7296, 'NAICS', 1657, 5414, 3, 1665, 54149, 4),
(7297, 'NAICS', 2137, 9211, 3, 2138, 921110, 5),
(7298, 'SIC', 4308, 20, 1, 3575, 3873, 4),
(7299, 'SIC', 4311, 52, 1, 3810, 5251, 4),
(7300, 'NAICS', 1725, 56, 1, 1766, 5616, 3),
(7301, 'NAICS', 117, 115, 2, 119, 11511, 4),
(7302, 'SEC', 2659, 6100, 2, 2668, 6162, 4),
(7303, 'SIC', 4313, 70, 1, 4066, 7371, 4),
(7304, 'SIC', 4037, 7290, 3, 4038, 7291, 4),
(7305, 'SIC', 3744, 5070, 3, 3747, 5075, 4),
(7306, 'SIC', 4313, 70, 1, 4213, 8630, 3),
(7307, 'NAICS', 56, 112, 2, 71, 112320, 5),
(7308, 'NAICS', 1015, 424, 2, 1061, 4246, 3),
(7309, 'SEC', 2791, 20, 1, 2448, 3663, 4),
(7310, 'NAICS', 1, 11, 1, 23, 1113, 3),
(7311, 'SIC', 2901, 1200, 2, 2902, 1220, 3),
(7312, 'NAICS', 1751, 56144, 4, 1750, 561440, 5),
(7313, 'SIC', 4310, 50, 1, 3788, 5160, 3),
(7314, 'SIC', 3167, 2600, 2, 3184, 2674, 4),
(7315, 'NAICS', 1741, 5614, 3, 1752, 561450, 5),
(7316, 'NAICS', 1850, 62, 1, 1881, 6215, 3),
(7317, 'SIC', 4309, 40, 1, 3683, 4813, 4),
(7318, 'SEC', 2677, 6300, 2, 2684, 6331, 4),
(7319, 'SIC', 4308, 20, 1, 3349, 3330, 3),
(7320, 'NAICS', 134, 2111, 3, 135, 21111, 4),
(7321, 'NAICS', 1624, 54, 1, 1687, 541720, 5),
(7322, 'SIC', 4308, 20, 1, 3596, 3991, 4),
(7323, 'SIC', 4305, 1, 1, 2830, 214, 4),
(7324, 'NAICS', 931, 423, 2, 948, 42331, 4),
(7325, 'NAICS', 2037, 81, 1, 2063, 811411, 5),
(7326, 'NAICS', 205, 23, 1, 217, 23622, 4),
(7327, 'NAICS', 1625, 541, 2, 1692, 541820, 5),
(7328, 'SIC', 4308, 20, 1, 3577, 3910, 3),
(7329, 'SIC', 3822, 5400, 2, 3827, 5430, 3),
(7330, 'NAICS', 205, 23, 1, 240, 23812, 4),
(7331, 'SIC', 4308, 20, 1, 3022, 2075, 4),
(7332, 'SIC', 2798, 100, 2, 2809, 134, 4),
(7333, 'SIC', 2847, 700, 2, 2864, 780, 3),
(7334, 'NAICS', 1689, 5418, 3, 1699, 54185, 4),
(7335, 'SIC', 4312, 60, 1, 3947, 6163, 4),
(7336, 'SIC', 2840, 270, 3, 2841, 271, 4),
(7337, 'SIC', 3167, 2600, 2, 3181, 2671, 4),
(7338, 'NAICS', 931, 423, 2, 990, 42374, 4),
(7339, 'NAICS', 1920, 624, 2, 1940, 624410, 5),
(7340, 'NAICS', 1, 11, 1, 127, 115210, 5),
(7341, 'NAICS', 1016, 4241, 3, 1019, 424120, 5),
(7342, 'NAICS', 1495, 5222, 3, 1497, 52221, 4),
(7343, 'NAICS', 1591, 532, 2, 1602, 53222, 4),
(7344, 'NAICS', 1571, 5311, 3, 1574, 531120, 5),
(7345, 'SIC', 4308, 20, 1, 3058, 2241, 4),
(7346, 'SEC', 2791, 20, 1, 2316, 2771, 4),
(7347, 'SEC', 2434, 3600, 2, 2448, 3663, 4),
(7348, 'NAICS', 183, 22111, 4, 191, 221118, 5),
(7349, 'NAICS', 1850, 62, 1, 1882, 62151, 4),
(7350, 'NAICS', 1480, 52, 1, 1501, 522291, 5),
(7351, 'SIC', 2896, 1080, 3, 2897, 1081, 4),
(7352, 'SIC', 4065, 7370, 3, 4068, 7373, 4),
(7353, 'SEC', 2458, 3700, 2, 2468, 3728, 4),
(7354, 'NAICS', 1625, 541, 2, 1627, 541110, 5),
(7355, 'NAICS', 970, 4235, 3, 971, 423510, 5),
(7356, 'NAICS', 1725, 56, 1, 1799, 56221, 4),
(7357, 'SIC', 3083, 2300, 2, 3108, 2380, 3),
(7358, 'NAICS', 1725, 56, 1, 1757, 561499, 5),
(7359, 'NAICS', 118, 1151, 3, 119, 11511, 4),
(7360, 'NAICS', 2135, 92, 1, 2195, 92613, 4),
(7361, 'SIC', 4311, 52, 1, 3892, 5932, 4),
(7362, 'SIC', 3633, 4300, 2, 3635, 4311, 4),
(7363, 'NAICS', 205, 23, 1, 271, 238390, 5),
(7364, 'SEC', 2630, 5700, 2, 2632, 5712, 4),
(7365, 'SIC', 4314, 90, 1, 4281, 9530, 3),
(7366, 'NAICS', 1488, 52211, 4, 1487, 522110, 5),
(7367, 'SEC', 2792, 40, 1, 2533, 4581, 4),
(7368, 'NAICS', 2048, 81119, 4, 2050, 811192, 5),
(7369, 'NAICS', 930, 42, 1, 967, 42346, 4),
(7370, 'NAICS', 975, 4236, 3, 978, 423620, 5),
(7371, 'NAICS', 2122, 81391, 4, 2121, 813910, 5),
(7372, 'SEC', 2790, 15, 1, 2229, 1500, 2),
(7373, 'NAICS', 2176, 924, 2, 2180, 924120, 5),
(7374, 'NAICS', 1462, 5179, 3, 1464, 517911, 5),
(7375, 'SIC', 4125, 7900, 2, 4133, 7940, 3),
(7376, 'SIC', 3337, 3300, 2, 3369, 3398, 4),
(7377, 'NAICS', 2071, 812, 2, 2086, 812310, 5),
(7378, 'SEC', 2302, 2700, 2, 2313, 2760, 3),
(7379, 'SIC', 4308, 20, 1, 3419, 3500, 2),
(7380, 'SIC', 4308, 20, 1, 3449, 3556, 4),
(7381, 'SIC', 4310, 50, 1, 3753, 5085, 4),
(7382, 'SEC', 2424, 3570, 3, 2425, 3571, 4),
(7383, 'SIC', 2850, 720, 3, 2852, 722, 4),
(7384, 'SEC', 2791, 20, 1, 2324, 2833, 4),
(7385, 'NAICS', 192, 22112, 4, 193, 221121, 5),
(7386, 'NAICS', 2037, 81, 1, 2127, 813940, 5),
(7387, 'NAICS', 43, 1119, 3, 52, 11199, 4),
(7388, 'SIC', 4306, 10, 1, 2932, 1474, 4),
(7389, 'SIC', 4311, 52, 1, 3804, 5200, 2),
(7390, 'SEC', 2677, 6300, 2, 2688, 6361, 4),
(7391, 'NAICS', 1541, 52412, 4, 1544, 524128, 5),
(7392, 'NAICS', 3, 1111, 3, 18, 111199, 5),
(7393, 'NAICS', 930, 42, 1, 991, 4238, 3),
(7394, 'NAICS', 2031, 7225, 3, 2032, 72251, 4),
(7395, 'SIC', 3167, 2600, 2, 3180, 2670, 3),
(7396, 'SIC', 4178, 8200, 2, 4191, 8299, 4),
(7397, 'NAICS', 1402, 51, 1, 1466, 518, 2),
(7398, 'NAICS', 1485, 522, 2, 1505, 522298, 5),
(7399, 'NAICS', 1726, 561, 2, 1781, 561740, 5),
(7400, 'SIC', 4308, 20, 1, 3532, 3716, 4),
(7401, 'NAICS', 1625, 541, 2, 1674, 541611, 5),
(7402, 'NAICS', 1402, 51, 1, 1445, 515111, 5),
(7403, 'SIC', 3837, 5500, 2, 3850, 5570, 3),
(7404, 'SEC', 2465, 3720, 3, 2467, 3724, 4),
(7405, 'NAICS', 1625, 541, 2, 1672, 5416, 3),
(7406, 'SEC', 2262, 2200, 2, 2263, 2210, 3),
(7407, 'SIC', 3041, 2100, 2, 3042, 2110, 3),
(7408, 'NAICS', 930, 42, 1, 959, 42342, 4),
(7409, 'NAICS', 1850, 62, 1, 1894, 622, 2),
(7410, 'NAICS', 955, 4234, 3, 965, 42345, 4),
(7411, 'NAICS', 2032, 72251, 4, 2034, 722513, 5),
(7412, 'SIC', 3480, 3600, 2, 3488, 3629, 4),
(7413, 'SIC', 4310, 50, 1, 3734, 5047, 4),
(7414, 'SIC', 3715, 5000, 2, 3720, 5015, 4),
(7415, 'NAICS', 58, 11211, 4, 59, 112111, 5),
(7416, 'NAICS', 1612, 5324, 3, 1616, 532420, 5),
(7417, 'NAICS', 1836, 6116, 3, 1844, 611691, 5),
(7418, 'NAICS', 2038, 811, 2, 2042, 811112, 5),
(7419, 'SIC', 3520, 3690, 3, 3525, 3699, 4),
(7420, 'SIC', 3977, 6500, 2, 3990, 6552, 4),
(7421, 'SIC', 4081, 7500, 2, 4085, 7515, 4),
(7422, 'NAICS', 208, 23611, 4, 210, 236116, 5),
(7423, 'NAICS', 2037, 81, 1, 2088, 812320, 5),
(7424, 'SEC', 2791, 20, 1, 2399, 3460, 3),
(7425, 'SIC', 3977, 6500, 2, 3985, 6530, 3),
(7426, 'SIC', 4139, 7990, 3, 4142, 7993, 4),
(7427, 'SIC', 4308, 20, 1, 3162, 2541, 4),
(7428, 'SEC', 2424, 3570, 3, 2430, 3579, 4),
(7429, 'SEC', 2691, 6400, 2, 2692, 6410, 3),
(7430, 'SIC', 4310, 50, 1, 3767, 5120, 3),
(7431, 'NAICS', 180, 22, 1, 188, 221115, 5),
(7432, 'NAICS', 1404, 5111, 3, 1409, 511130, 5),
(7433, 'NAICS', 1625, 541, 2, 1628, 54111, 4),
(7434, 'SIC', 4308, 20, 1, 3522, 3692, 4),
(7435, 'SIC', 3200, 2750, 3, 3201, 2752, 4),
(7436, 'SEC', 2795, 60, 1, 2652, 6022, 4),
(7437, 'SIC', 3299, 3190, 3, 3300, 3199, 4),
(7438, 'SIC', 3552, 3800, 2, 3556, 3821, 4),
(7439, 'SIC', 3631, 4230, 3, 3632, 4231, 4),
(7440, 'SIC', 3854, 5600, 2, 3858, 5621, 4),
(7441, 'NAICS', 1942, 71, 1, 1991, 713910, 5),
(7442, 'NAICS', 2103, 813, 2, 2107, 8132, 3),
(7443, 'SIC', 4081, 7500, 2, 4094, 7537, 4),
(7444, 'SIC', 3086, 2320, 3, 3087, 2321, 4),
(7445, 'SIC', 3214, 2800, 2, 3244, 2875, 4),
(7446, 'SEC', 2610, 5300, 2, 2614, 5331, 4),
(7447, 'NAICS', 952, 42333, 4, 951, 423330, 5),
(7448, 'SIC', 4308, 20, 1, 2990, 2023, 4),
(7449, 'NAICS', 2085, 8123, 3, 2092, 812332, 5),
(7450, 'SIC', 4308, 20, 1, 3102, 2353, 4),
(7451, 'SIC', 3371, 3400, 2, 3416, 3497, 4),
(7452, 'SIC', 3680, 4800, 2, 3681, 4810, 3),
(7453, 'NAICS', 1820, 6113, 3, 1822, 61131, 4),
(7454, 'SIC', 3261, 3000, 2, 3271, 3069, 4),
(7455, 'SIC', 3636, 4400, 2, 3650, 4491, 4),
(7456, 'SIC', 4311, 52, 1, 3849, 5561, 4),
(7457, 'SIC', 3917, 6000, 2, 3919, 6011, 4),
(7458, 'NAICS', 119, 11511, 4, 124, 115115, 5),
(7459, 'NAICS', 2113, 81331, 4, 2116, 813319, 5),
(7460, 'NAICS', 2188, 926, 2, 2196, 926140, 5),
(7461, 'SEC', 2795, 60, 1, 2673, 6220, 3),
(7462, 'SIC', 3948, 6200, 2, 3950, 6211, 4),
(7463, 'NAICS', 1725, 56, 1, 1783, 561790, 5),
(7464, 'SEC', 2792, 40, 1, 2547, 4833, 4),
(7465, 'SIC', 4314, 90, 1, 4293, 9650, 3),
(7466, 'SIC', 3667, 4700, 2, 3677, 4783, 4),
(7467, 'SIC', 4313, 70, 1, 4074, 7379, 4),
(7468, 'NAICS', 931, 423, 2, 1005, 423910, 5),
(7469, 'SIC', 4305, 1, 1, 2843, 273, 4),
(7470, 'SEC', 2659, 6100, 2, 4324, 6190, 3),
(7471, 'SIC', 3337, 3300, 2, 3362, 3360, 3),
(7472, 'NAICS', 1706, 5419, 3, 1717, 54199, 4),
(7473, 'SIC', 4125, 7900, 2, 4127, 7911, 4),
(7474, 'SEC', 2791, 20, 1, 2366, 3270, 3),
(7475, 'SEC', 2742, 7820, 3, 2744, 7829, 4),
(7476, 'NAICS', 1657, 5414, 3, 1664, 541490, 5),
(7477, 'SIC', 4313, 70, 1, 4070, 7375, 4),
(7478, 'SEC', 2459, 3710, 3, 2464, 3716, 4),
(7479, 'NAICS', 206, 236, 2, 217, 23622, 4),
(7480, 'NAICS', 1785, 5619, 3, 1791, 56199, 4),
(7481, 'NAICS', 2150, 922, 2, 2163, 92216, 4),
(7482, 'SIC', 3934, 6090, 3, 3935, 6091, 4),
(7483, 'SEC', 2795, 60, 1, 4327, 6770, 3),
(7484, 'SIC', 4313, 70, 1, 4230, 8730, 3),
(7485, 'SIC', 4100, 7600, 2, 4101, 7620, 3),
(7486, 'NAICS', 2052, 8112, 3, 2054, 811211, 5),
(7487, 'SIC', 3098, 2340, 3, 3100, 2342, 4),
(7488, 'SIC', 4308, 20, 1, 3502, 3647, 4),
(7489, 'SIC', 3854, 5600, 2, 3868, 5699, 4),
(7490, 'SIC', 4308, 20, 1, 3285, 3130, 3),
(7491, 'NAICS', 1, 11, 1, 56, 112, 2),
(7492, 'SIC', 3696, 4920, 3, 3697, 4922, 4),
(7493, 'NAICS', 930, 42, 1, 1078, 42491, 4),
(7494, 'SIC', 4314, 90, 1, 4262, 9223, 4),
(7495, 'NAICS', 181, 221, 2, 187, 221114, 5),
(7496, 'SEC', 2476, 3800, 2, 2481, 3822, 4),
(7497, 'NAICS', 219, 2371, 3, 225, 23713, 4),
(7498, 'NAICS', 2037, 81, 1, 2101, 812990, 5),
(7499, 'NAICS', 2071, 812, 2, 2090, 81233, 4),
(7500, 'NAICS', 2131, 814, 2, 2134, 81411, 4),
(7501, 'SIC', 4309, 40, 1, 3631, 4230, 3),
(7502, 'NAICS', 28, 11133, 4, 33, 111335, 5),
(7503, 'NAICS', 1766, 5616, 3, 1773, 561622, 5),
(7504, 'SEC', 2699, 6530, 3, 2700, 6531, 4),
(7505, 'SIC', 3301, 3200, 2, 3318, 3262, 4),
(7506, 'SIC', 3214, 2800, 2, 3243, 2874, 4),
(7507, 'NAICS', 132, 21, 1, 173, 2131, 3),
(7508, 'NAICS', 1480, 52, 1, 1505, 522298, 5),
(7509, 'SIC', 4268, 9400, 2, 4272, 9431, 4),
(7510, 'SIC', 4125, 7900, 2, 4140, 7991, 4),
(7511, 'SIC', 3774, 5140, 3, 3777, 5143, 4),
(7512, 'NAICS', 1726, 561, 2, 1751, 56144, 4),
(7513, 'NAICS', 1851, 621, 2, 1873, 62141, 4),
(7514, 'NAICS', 1985, 7132, 3, 1986, 713210, 5),
(7515, 'SIC', 4306, 10, 1, 2906, 1231, 4),
(7516, 'NAICS', 1689, 5418, 3, 1694, 541830, 5),
(7517, 'SIC', 2948, 1600, 2, 2952, 1622, 4),
(7518, 'SEC', 2630, 5700, 2, 2636, 5735, 4),
(7519, 'SEC', 2725, 7370, 3, 2730, 7377, 4),
(7520, 'SEC', 2791, 20, 1, 2460, 3711, 4),
(7521, 'SIC', 2955, 1700, 2, 2981, 1799, 4),
(7522, 'SEC', 2797, 90, 1, 2787, 9721, 4),
(7523, 'NAICS', 1015, 424, 2, 1047, 42446, 4),
(7524, 'SEC', 2458, 3700, 2, 2465, 3720, 3),
(7525, 'SIC', 4308, 20, 1, 3078, 2295, 4),
(7526, 'NAICS', 1402, 51, 1, 1448, 51512, 4),
(7527, 'NAICS', 1526, 5239, 3, 1532, 52393, 4),
(7528, 'SEC', 2677, 6300, 2, 2680, 6320, 3),
(7529, 'SIC', 4308, 20, 1, 3036, 2095, 4),
(7530, 'SIC', 4311, 52, 1, 3860, 5632, 4),
(7531, 'SIC', 4308, 20, 1, 3067, 2260, 3),
(7532, 'SIC', 3338, 3310, 3, 3340, 3313, 4),
(7533, 'NAICS', 205, 23, 1, 268, 23834, 4),
(7534, 'SEC', 2791, 20, 1, 2472, 3750, 3),
(7535, 'SIC', 3190, 2700, 2, 3192, 2711, 4),
(7536, 'SIC', 3934, 6090, 3, 3936, 6099, 4),
(7537, 'NAICS', 1480, 52, 1, 1517, 523120, 5),
(7538, 'SEC', 2568, 5000, 2, 2588, 5090, 3),
(7539, 'SIC', 3511, 3670, 3, 3517, 3677, 4),
(7540, 'NAICS', 138, 212, 2, 154, 212291, 5),
(7541, 'NAICS', 1621, 5331, 3, 1623, 53311, 4),
(7542, 'SEC', 2791, 20, 1, 2502, 3911, 4),
(7543, 'SEC', 2415, 3550, 3, 2416, 3555, 4),
(7544, 'NAICS', 2103, 813, 2, 2104, 8131, 3),
(7545, 'SIC', 4311, 52, 1, 3856, 5611, 4),
(7546, 'SEC', 2591, 5100, 2, 2597, 5141, 4),
(7547, 'SIC', 3948, 6200, 2, 3955, 6280, 3),
(7548, 'NAICS', 1569, 53, 1, 1620, 533, 2),
(7549, 'NAICS', 1631, 54119, 4, 1632, 541191, 5),
(7550, 'SIC', 4308, 20, 1, 3200, 2750, 3),
(7551, 'NAICS', 2005, 7211, 3, 2009, 72112, 4),
(7552, 'NAICS', 2052, 8112, 3, 2056, 811213, 5),
(7553, 'SIC', 3261, 3000, 2, 3269, 3060, 3),
(7554, 'SIC', 4306, 10, 1, 2887, 1020, 3),
(7555, 'SIC', 4308, 20, 1, 3042, 2110, 3),
(7556, 'SIC', 3552, 3800, 2, 3575, 3873, 4),
(7557, 'NAICS', 931, 423, 2, 987, 423730, 5),
(7558, 'NAICS', 1485, 522, 2, 1501, 522291, 5),
(7559, 'SIC', 3645, 4480, 3, 3647, 4482, 4),
(7560, 'NAICS', 2155, 92212, 4, 2154, 922120, 5),
(7561, 'NAICS', 1725, 56, 1, 1731, 561210, 5),
(7562, 'SIC', 4308, 20, 1, 3218, 2816, 4),
(7563, 'SIC', 2799, 110, 3, 2802, 115, 4),
(7564, 'NAICS', 1, 11, 1, 100, 113110, 5),
(7565, 'NAICS', 1719, 551, 2, 1720, 5511, 3),
(7566, 'SEC', 2791, 20, 1, 2381, 3357, 4),
(7567, 'SIC', 2918, 1400, 2, 2935, 1480, 3),
(7568, 'SIC', 3762, 5100, 2, 3784, 5150, 3),
(7569, 'NAICS', 1536, 524, 2, 1541, 52412, 4),
(7570, 'SIC', 3214, 2800, 2, 3240, 2869, 4),
(7571, 'SEC', 2796, 70, 1, 2715, 7311, 4),
(7572, 'SEC', 2791, 20, 1, 2268, 2253, 4),
(7573, 'SIC', 4310, 50, 1, 3796, 5182, 4),
(7574, 'SIC', 3715, 5000, 2, 3727, 5033, 4),
(7575, 'SIC', 2955, 1700, 2, 2975, 1790, 3),
(7576, 'SIC', 4311, 52, 1, 3877, 5730, 3),
(7577, 'SIC', 4308, 20, 1, 3277, 3085, 4),
(7578, 'SIC', 3649, 4490, 3, 3652, 4493, 4),
(7579, 'SIC', 3729, 5040, 3, 3734, 5047, 4),
(7580, 'NAICS', 117, 115, 2, 118, 1151, 3),
(7581, 'NAICS', 2112, 8133, 3, 2116, 813319, 5),
(7582, 'SIC', 4308, 20, 1, 3062, 2253, 4),
(7583, 'NAICS', 1921, 6241, 3, 1923, 62411, 4),
(7584, 'SIC', 2868, 800, 2, 2873, 850, 3),
(7585, 'SIC', 3086, 2320, 3, 3092, 2329, 4),
(7586, 'SIC', 4308, 20, 1, 3339, 3312, 4),
(7587, 'NAICS', 2072, 8121, 3, 2076, 812113, 5),
(7588, 'SIC', 3190, 2700, 2, 3200, 2750, 3),
(7589, 'NAICS', 138, 212, 2, 169, 212392, 5),
(7590, 'SIC', 4309, 40, 1, 3601, 4000, 2),
(7591, 'SIC', 4117, 7820, 3, 4118, 7822, 4),
(7592, 'NAICS', 56, 112, 2, 75, 112340, 5),
(7593, 'SIC', 4313, 70, 1, 4169, 8080, 3),
(7594, 'NAICS', 1850, 62, 1, 1876, 62149, 4),
(7595, 'SEC', 2613, 5330, 3, 2614, 5331, 4),
(7596, 'SEC', 2795, 60, 1, 2689, 6390, 3),
(7597, 'NAICS', 941, 4232, 3, 945, 42322, 4),
(7598, 'NAICS', 2135, 92, 1, 2206, 928110, 5),
(7599, 'NAICS', 2204, 928, 2, 2207, 92811, 4),
(7600, 'SEC', 2342, 3000, 2, 2352, 3089, 4),
(7601, 'NAICS', 1725, 56, 1, 1752, 561450, 5),
(7602, 'NAICS', 2071, 812, 2, 2098, 812922, 5),
(7603, 'SIC', 2798, 100, 2, 2823, 190, 3),
(7604, 'NAICS', 930, 42, 1, 1081, 424930, 5),
(7605, 'NAICS', 1851, 621, 2, 1877, 621491, 5),
(7606, 'SIC', 4308, 20, 1, 3192, 2711, 4),
(7607, 'SIC', 3301, 3200, 2, 3312, 3251, 4),
(7608, 'NAICS', 1, 11, 1, 104, 11321, 4),
(7609, 'SIC', 2925, 1440, 3, 2927, 1446, 4),
(7610, 'SIC', 4247, 9100, 2, 4252, 9130, 3),
(7611, 'SIC', 4307, 15, 1, 2945, 1540, 3),
(7612, 'SIC', 4308, 20, 1, 3373, 3411, 4),
(7613, 'SIC', 4313, 70, 1, 4132, 7933, 4),
(7614, 'NAICS', 1526, 5239, 3, 1531, 523930, 5),
(7615, 'SIC', 4153, 8040, 3, 4155, 8042, 4),
(7616, 'NAICS', 1850, 62, 1, 1911, 623220, 5),
(7617, 'SEC', 2791, 20, 1, 2488, 3840, 3),
(7618, 'SEC', 2791, 20, 1, 2508, 3949, 4),
(7619, 'NAICS', 930, 42, 1, 956, 423410, 5),
(7620, 'NAICS', 2189, 9261, 3, 2193, 92612, 4),
(7621, 'SIC', 3020, 2070, 3, 3022, 2075, 4),
(7622, 'SEC', 2527, 4510, 3, 2528, 4512, 4),
(7623, 'SIC', 3214, 2800, 2, 3223, 2823, 4),
(7624, 'NAICS', 1657, 5414, 3, 1661, 54142, 4),
(7625, 'SIC', 4302, 9900, 2, 4304, 9999, 4),
(7626, 'SIC', 4139, 7990, 3, 4143, 7996, 4),
(7627, 'NAICS', 3, 1111, 3, 4, 111110, 5),
(7628, 'SEC', 2794, 52, 1, 2635, 5734, 4),
(7629, 'SIC', 4308, 20, 1, 3170, 2620, 3),
(7630, 'NAICS', 2071, 812, 2, 2075, 812112, 5),
(7631, 'SIC', 3749, 5080, 3, 3753, 5085, 4),
(7632, 'SIC', 4284, 9600, 2, 4287, 9620, 3),
(7633, 'SIC', 3907, 5980, 3, 3910, 5989, 4),
(7634, 'NAICS', 930, 42, 1, 1001, 42385, 4),
(7635, 'SIC', 3854, 5600, 2, 3860, 5632, 4),
(7636, 'SIC', 4308, 20, 1, 3085, 2311, 4),
(7637, 'NAICS', 132, 21, 1, 150, 21223, 4),
(7638, 'SEC', 2539, 4800, 2, 2545, 4830, 3),
(7639, 'SIC', 4309, 40, 1, 3624, 4214, 4),
(7640, 'SIC', 3993, 6710, 3, 3994, 6712, 4),
(7641, 'NAICS', 1536, 524, 2, 1546, 52413, 4),
(7642, 'SIC', 2982, 2000, 2, 3025, 2079, 4),
(7643, 'NAICS', 1706, 5419, 3, 1710, 541921, 5),
(7644, 'NAICS', 2040, 81111, 4, 2042, 811112, 5),
(7645, 'NAICS', 173, 2131, 3, 179, 213115, 5),
(7646, 'SEC', 2552, 4900, 2, 2553, 4910, 3),
(7647, 'NAICS', 1850, 62, 1, 1926, 624190, 5),
(7648, 'SEC', 2795, 60, 1, 2683, 6330, 3),
(7649, 'SIC', 4308, 20, 1, 3171, 2621, 4),
(7650, 'NAICS', 2071, 812, 2, 2074, 812111, 5),
(7651, 'SIC', 2875, 900, 2, 2883, 971, 4),
(7652, 'NAICS', 183, 22111, 4, 190, 221117, 5),
(7653, 'SIC', 3854, 5600, 2, 3856, 5611, 4),
(7654, 'SIC', 2850, 720, 3, 2851, 721, 4),
(7655, 'NAICS', 1942, 71, 1, 1945, 711110, 5),
(7656, 'SIC', 4313, 70, 1, 4058, 7350, 3),
(7657, 'NAICS', 235, 238, 2, 265, 238330, 5),
(7658, 'NAICS', 1575, 53112, 4, 1574, 531120, 5),
(7659, 'NAICS', 56, 112, 2, 95, 11293, 4),
(7660, 'NAICS', 2135, 92, 1, 2199, 92615, 4),
(7661, 'NAICS', 205, 23, 1, 238, 23811, 4),
(7662, 'NAICS', 1625, 541, 2, 1649, 541350, 5),
(7663, 'NAICS', 1726, 561, 2, 1737, 561320, 5),
(7664, 'SEC', 2539, 4800, 2, 2548, 4840, 3),
(7665, 'SIC', 4311, 52, 1, 3884, 5812, 4),
(7666, 'SIC', 4307, 15, 1, 2944, 1531, 4),
(7667, 'SIC', 3301, 3200, 2, 3311, 3250, 3),
(7668, 'SIC', 3869, 5700, 2, 3873, 5714, 4),
(7669, 'SIC', 4125, 7900, 2, 4141, 7992, 4),
(7670, 'SIC', 3301, 3200, 2, 3310, 3241, 4),
(7671, 'NAICS', 1420, 5121, 3, 1427, 512132, 5),
(7672, 'NAICS', 1536, 524, 2, 1542, 524126, 5),
(7673, 'SEC', 2789, 10, 1, 2228, 1400, 2),
(7674, 'SIC', 4311, 52, 1, 3868, 5699, 4),
(7675, 'SEC', 2731, 7380, 3, 2734, 7389, 4),
(7676, 'NAICS', 1402, 51, 1, 1435, 51222, 4),
(7677, 'SIC', 4308, 20, 1, 3155, 2519, 4),
(7678, 'NAICS', 1726, 561, 2, 1765, 561599, 5),
(7679, 'SIC', 3480, 3600, 2, 3508, 3661, 4),
(7680, 'NAICS', 1780, 56173, 4, 1779, 561730, 5),
(7681, 'NAICS', 1425, 51213, 4, 1426, 512131, 5),
(7682, 'SIC', 4308, 20, 1, 3120, 2395, 4),
(7683, 'SIC', 4308, 20, 1, 2989, 2022, 4),
(7684, 'SIC', 4100, 7600, 2, 4108, 7641, 4),
(7685, 'NAICS', 2038, 811, 2, 2061, 8114, 3),
(7686, 'SIC', 3190, 2700, 2, 3201, 2752, 4),
(7687, 'SEC', 2559, 4930, 3, 2560, 4931, 4),
(7688, 'SIC', 3161, 2540, 3, 3162, 2541, 4),
(7689, 'SIC', 4308, 20, 1, 3471, 3585, 4),
(7690, 'SIC', 4308, 20, 1, 3340, 3313, 4),
(7691, 'NAICS', 1470, 519, 2, 1471, 5191, 3),
(7692, 'SIC', 4305, 1, 1, 2845, 290, 3),
(7693, 'SIC', 2840, 270, 3, 2843, 273, 4),
(7694, 'SEC', 2792, 40, 1, 2554, 4911, 4),
(7695, 'NAICS', 1624, 54, 1, 1691, 54181, 4),
(7696, 'SEC', 2640, 5900, 2, 2645, 5945, 4),
(7697, 'SIC', 4308, 20, 1, 3072, 2273, 4),
(7698, 'SIC', 4308, 20, 1, 3517, 3677, 4),
(7699, 'SEC', 2342, 3000, 2, 2346, 3021, 4),
(7700, 'NAICS', 1741, 5614, 3, 1757, 561499, 5),
(7701, 'SEC', 2791, 20, 1, 2477, 3810, 3),
(7702, 'NAICS', 2, 111, 2, 15, 11116, 4),
(7703, 'NAICS', 1015, 424, 2, 1052, 424490, 5),
(7704, 'SIC', 4223, 8700, 2, 4238, 8743, 4),
(7705, 'NAICS', 1536, 524, 2, 1551, 524291, 5),
(7706, 'SIC', 3689, 4840, 3, 3690, 4841, 4),
(7707, 'NAICS', 156, 2123, 3, 171, 212399, 5),
(7708, 'NAICS', 138, 212, 2, 156, 2123, 3),
(7709, 'NAICS', 1625, 541, 2, 1694, 541830, 5),
(7710, 'SIC', 4305, 1, 1, 2880, 920, 3),
(7711, 'NAICS', 1642, 54131, 4, 1641, 541310, 5),
(7712, 'SIC', 3715, 5000, 2, 3736, 5049, 4),
(7713, 'NAICS', 1858, 62121, 4, 1857, 621210, 5),
(7714, 'NAICS', 2135, 92, 1, 2148, 921190, 5),
(7715, 'SIC', 4247, 9100, 2, 4251, 9121, 4),
(7716, 'SIC', 4308, 20, 1, 3117, 2392, 4),
(7717, 'SIC', 3338, 3310, 3, 3339, 3312, 4),
(7718, 'SIC', 4308, 20, 1, 3103, 2360, 3),
(7719, 'SIC', 4308, 20, 1, 3364, 3364, 4),
(7720, 'SIC', 4040, 7300, 2, 4079, 7384, 4),
(7721, 'SIC', 4297, 9700, 2, 4301, 9721, 4),
(7722, 'NAICS', 1625, 541, 2, 1642, 54131, 4),
(7723, 'SEC', 2659, 6100, 2, 2665, 6153, 4),
(7724, 'SIC', 4305, 1, 1, 2841, 271, 4),
(7725, 'NAICS', 1625, 541, 2, 1652, 54136, 4),
(7726, 'SIC', 3050, 2200, 2, 3073, 2280, 3),
(7727, 'SIC', 4308, 20, 1, 3556, 3821, 4),
(7728, 'NAICS', 1480, 52, 1, 1491, 522130, 5),
(7729, 'SEC', 2795, 60, 1, 2697, 6513, 4),
(7730, 'SIC', 4308, 20, 1, 3400, 3469, 4),
(7731, 'SIC', 3246, 2890, 3, 3250, 2895, 4),
(7732, 'SEC', 2276, 2400, 2, 2279, 2430, 3),
(7733, 'NAICS', 1624, 54, 1, 1673, 54161, 4),
(7734, 'NAICS', 1, 11, 1, 96, 112990, 5),
(7735, 'SIC', 4305, 1, 1, 2809, 134, 4),
(7736, 'NAICS', 2167, 9231, 3, 2171, 92312, 4),
(7737, 'NAICS', 1404, 5111, 3, 1412, 51114, 4),
(7738, 'SIC', 4309, 40, 1, 3630, 4226, 4),
(7739, 'NAICS', 2, 111, 2, 47, 11192, 4),
(7740, 'SIC', 4308, 20, 1, 3273, 3081, 4),
(7741, 'SIC', 4193, 8320, 3, 4194, 8322, 4),
(7742, 'NAICS', 2004, 721, 2, 2015, 721211, 5),
(7743, 'NAICS', 970, 4235, 3, 974, 42352, 4),
(7744, 'SEC', 2796, 70, 1, 2759, 8062, 4),
(7745, 'SIC', 4312, 60, 1, 3925, 6030, 3),
(7746, 'SIC', 4313, 70, 1, 4100, 7600, 2),
(7747, 'NAICS', 180, 22, 1, 182, 2211, 3),
(7748, 'NAICS', 930, 42, 1, 980, 423690, 5),
(7749, 'SEC', 2458, 3700, 2, 2475, 3790, 3),
(7750, 'SIC', 3636, 4400, 2, 3643, 4440, 3),
(7751, 'NAICS', 1486, 5221, 3, 1492, 52213, 4),
(7752, 'NAICS', 181, 221, 2, 200, 22131, 4),
(7753, 'SIC', 4041, 7310, 3, 4042, 7311, 4),
(7754, 'NAICS', 1688, 54172, 4, 1687, 541720, 5),
(7755, 'SIC', 2943, 1530, 3, 2944, 1531, 4),
(7756, 'SIC', 3794, 5180, 3, 3796, 5182, 4),
(7757, 'SIC', 4241, 8800, 2, 4243, 8811, 4),
(7758, 'NAICS', 1944, 7111, 3, 1952, 71119, 4),
(7759, 'NAICS', 162, 21232, 4, 163, 212321, 5),
(7760, 'SEC', 2794, 52, 1, 2610, 5300, 2),
(7761, 'SEC', 2796, 70, 1, 2773, 8600, 2),
(7762, 'SIC', 3050, 2200, 2, 3055, 2230, 3),
(7763, 'NAICS', 1942, 71, 1, 1985, 7132, 3),
(7764, 'SEC', 2791, 20, 1, 2478, 3812, 4),
(7765, 'SIC', 4308, 20, 1, 3201, 2752, 4),
(7766, 'SIC', 4247, 9100, 2, 4254, 9190, 3),
(7767, 'SIC', 4312, 60, 1, 3973, 6399, 4),
(7768, 'SEC', 2694, 6500, 2, 2696, 6512, 4),
(7769, 'SIC', 4307, 15, 1, 2976, 1791, 4),
(7770, 'SIC', 3804, 5200, 2, 3806, 5211, 4),
(7771, 'NAICS', 1887, 62161, 4, 1886, 621610, 5),
(7772, 'SIC', 3050, 2200, 2, 3052, 2211, 4),
(7773, 'SIC', 3587, 3950, 3, 3591, 3955, 4),
(7774, 'SIC', 4311, 52, 1, 3889, 5920, 3),
(7775, 'NAICS', 56, 112, 2, 92, 112920, 5),
(7776, 'SIC', 4113, 7800, 2, 4122, 7833, 4),
(7777, 'SIC', 3931, 6080, 3, 3933, 6082, 4),
(7778, 'NAICS', 1920, 624, 2, 1939, 6244, 3),
(7779, 'SIC', 3526, 3700, 2, 3548, 3790, 3),
(7780, 'NAICS', 1, 11, 1, 108, 114, 2),
(7781, 'NAICS', 1672, 5416, 3, 1676, 541613, 5),
(7782, 'NAICS', 108, 114, 2, 113, 114119, 5),
(7783, 'SEC', 2738, 7800, 2, 2740, 7812, 4),
(7784, 'NAICS', 1442, 515, 2, 1443, 5151, 3),
(7785, 'NAICS', 117, 115, 2, 127, 115210, 5),
(7786, 'NAICS', 1850, 62, 1, 1864, 621330, 5),
(7787, 'SEC', 2793, 50, 1, 2575, 5045, 4),
(7788, 'SIC', 4308, 20, 1, 3301, 3200, 2),
(7789, 'NAICS', 1012, 42394, 4, 1011, 423940, 5),
(7790, 'SIC', 4201, 8390, 3, 4202, 8399, 4),
(7791, 'SEC', 2791, 20, 1, 2440, 3630, 3),
(7792, 'SIC', 3526, 3700, 2, 3543, 3751, 4),
(7793, 'SIC', 4310, 50, 1, 3739, 5052, 4),
(7794, 'SIC', 3958, 6300, 2, 3963, 6324, 4),
(7795, 'SIC', 3252, 2900, 2, 3253, 2910, 3),
(7796, 'SIC', 4313, 70, 1, 4190, 8290, 3),
(7797, 'SIC', 3667, 4700, 2, 3674, 4740, 3),
(7798, 'NAICS', 2135, 92, 1, 2149, 92119, 4),
(7799, 'SIC', 3886, 5900, 2, 3896, 5943, 4),
(7800, 'SIC', 2834, 250, 3, 2836, 252, 4),
(7801, 'SIC', 4308, 20, 1, 3196, 2731, 4),
(7802, 'NAICS', 205, 23, 1, 255, 23821, 4),
(7803, 'NAICS', 1726, 561, 2, 1785, 5619, 3),
(7804, 'SIC', 4308, 20, 1, 3209, 2782, 4),
(7805, 'SIC', 4313, 70, 1, 4033, 7250, 3),
(7806, 'NAICS', 1569, 53, 1, 1590, 53139, 4),
(7807, 'NAICS', 1842, 61163, 4, 1841, 611630, 5),
(7808, 'SIC', 3480, 3600, 2, 3490, 3631, 4),
(7809, 'SIC', 4305, 1, 1, 2876, 910, 3),
(7810, 'SIC', 3893, 5940, 3, 3901, 5948, 4),
(7811, 'SIC', 4308, 20, 1, 3594, 3965, 4),
(7812, 'NAICS', 1625, 541, 2, 1660, 541420, 5),
(7813, 'SIC', 4305, 1, 1, 2875, 900, 2),
(7814, 'SIC', 2909, 1300, 2, 2917, 1389, 4),
(7815, 'NAICS', 133, 211, 2, 136, 211111, 5),
(7816, 'NAICS', 2, 111, 2, 12, 111150, 5),
(7817, 'SIC', 4308, 20, 1, 3454, 3563, 4),
(7818, 'SIC', 2921, 1420, 3, 2923, 1423, 4),
(7819, 'SIC', 3180, 2670, 3, 3182, 2672, 4),
(7820, 'SIC', 2918, 1400, 2, 2919, 1410, 3),
(7821, 'NAICS', 1625, 541, 2, 1638, 541214, 5),
(7822, 'SEC', 2371, 3300, 2, 2372, 3310, 3),
(7823, 'SIC', 3371, 3400, 2, 3398, 3465, 4),
(7824, 'NAICS', 1850, 62, 1, 1863, 62132, 4),
(7825, 'NAICS', 930, 42, 1, 1048, 424470, 5),
(7826, 'NAICS', 1569, 53, 1, 1618, 532490, 5),
(7827, 'SIC', 3480, 3600, 2, 3511, 3670, 3),
(7828, 'SIC', 3362, 3360, 3, 3365, 3365, 4),
(7829, 'SIC', 4310, 50, 1, 3776, 5142, 4),
(7830, 'SIC', 4081, 7500, 2, 4082, 7510, 3),
(7831, 'SIC', 4308, 20, 1, 3232, 2842, 4),
(7832, 'NAICS', 1624, 54, 1, 1657, 5414, 3),
(7833, 'NAICS', 2150, 922, 2, 2160, 922150, 5),
(7834, 'SIC', 3380, 3430, 3, 3382, 3432, 4),
(7835, 'NAICS', 205, 23, 1, 228, 23721, 4),
(7836, 'NAICS', 1480, 52, 1, 1495, 5222, 3),
(7837, 'SIC', 3715, 5000, 2, 3743, 5065, 4),
(7838, 'NAICS', 56, 112, 2, 81, 11241, 4),
(7839, 'SIC', 3190, 2700, 2, 3209, 2782, 4),
(7840, 'NAICS', 1481, 521, 2, 1484, 52111, 4),
(7841, 'NAICS', 1570, 531, 2, 1578, 531190, 5),
(7842, 'NAICS', 1850, 62, 1, 1879, 621493, 5),
(7843, 'NAICS', 1851, 621, 2, 1865, 62133, 4),
(7844, 'SIC', 3190, 2700, 2, 3196, 2731, 4),
(7845, 'SEC', 2790, 15, 1, 2237, 1700, 2),
(7846, 'SIC', 3480, 3600, 2, 3503, 3648, 4),
(7847, 'SIC', 4311, 52, 1, 3898, 5945, 4),
(7848, 'NAICS', 1541, 52412, 4, 1543, 524127, 5),
(7849, 'SEC', 2498, 3870, 3, 2499, 3873, 4),
(7850, 'NAICS', 1725, 56, 1, 1787, 56191, 4),
(7851, 'SIC', 3917, 6000, 2, 3918, 6010, 3),
(7852, 'SIC', 4308, 20, 1, 2988, 2021, 4),
(7853, 'SIC', 3301, 3200, 2, 3326, 3274, 4),
(7854, 'NAICS', 1570, 531, 2, 1571, 5311, 3),
(7855, 'SEC', 2792, 40, 1, 2550, 4890, 3),
(7856, 'SIC', 3272, 3080, 3, 3274, 3082, 4),
(7857, 'SIC', 4309, 40, 1, 3619, 4173, 4),
(7858, 'SIC', 4035, 7260, 3, 4036, 7261, 4),
(7859, 'SIC', 2798, 100, 2, 2814, 171, 4),
(7860, 'NAICS', 1035, 4244, 3, 1043, 42444, 4),
(7861, 'NAICS', 2031, 7225, 3, 2034, 722513, 5),
(7862, 'SIC', 3526, 3700, 2, 3527, 3710, 3),
(7863, 'SEC', 2458, 3700, 2, 2463, 3715, 4),
(7864, 'SIC', 4308, 20, 1, 3581, 3930, 3),
(7865, 'NAICS', 138, 212, 2, 171, 212399, 5),
(7866, 'NAICS', 1763, 56159, 4, 1764, 561591, 5),
(7867, 'SIC', 3507, 3660, 3, 3509, 3663, 4),
(7868, 'SIC', 4310, 50, 1, 3729, 5040, 3),
(7869, 'NAICS', 1, 11, 1, 93, 11292, 4),
(7870, 'NAICS', 1570, 531, 2, 1587, 531320, 5),
(7871, 'NAICS', 2020, 722, 2, 2029, 722410, 5),
(7872, 'NAICS', 1894, 622, 2, 1901, 6223, 3),
(7873, 'NAICS', 2159, 92214, 4, 2158, 922140, 5),
(7874, 'NAICS', 2053, 81121, 4, 2055, 811212, 5),
(7875, 'NAICS', 1026, 4243, 3, 1028, 42431, 4),
(7876, 'NAICS', 1661, 54142, 4, 1660, 541420, 5),
(7877, 'SEC', 2418, 3560, 3, 2422, 3567, 4),
(7878, 'NAICS', 1569, 53, 1, 1612, 5324, 3),
(7879, 'SIC', 3636, 4400, 2, 3642, 4432, 4),
(7880, 'NAICS', 1624, 54, 1, 1626, 5411, 3),
(7881, 'SIC', 3555, 3820, 3, 3561, 3826, 4),
(7882, 'SIC', 3409, 3490, 3, 3414, 3495, 4),
(7883, 'NAICS', 1850, 62, 1, 1935, 62423, 4),
(7884, 'SIC', 4312, 60, 1, 3995, 6719, 4),
(7885, 'SIC', 4178, 8200, 2, 4187, 8243, 4),
(7886, 'NAICS', 1625, 541, 2, 1646, 54133, 4),
(7887, 'NAICS', 955, 4234, 3, 960, 423430, 5),
(7888, 'NAICS', 1402, 51, 1, 1465, 517919, 5),
(7889, 'SIC', 3663, 4610, 3, 3665, 4613, 4),
(7890, 'SIC', 4313, 70, 1, 4188, 8244, 4),
(7891, 'NAICS', 3, 1111, 3, 14, 111160, 5),
(7892, 'SIC', 3419, 3500, 2, 3477, 3594, 4),
(7893, 'NAICS', 1990, 7139, 3, 1992, 71391, 4),
(7894, 'SIC', 4308, 20, 1, 3226, 2833, 4),
(7895, 'NAICS', 1919, 62399, 4, 1918, 623990, 5),
(7896, 'NAICS', 1943, 711, 2, 1956, 711212, 5),
(7897, 'NAICS', 1089, 425, 2, 1091, 425110, 5),
(7898, 'SIC', 4308, 20, 1, 3507, 3660, 3),
(7899, 'SEC', 2791, 20, 1, 2443, 3650, 3),
(7900, 'SIC', 4081, 7500, 2, 4096, 7539, 4),
(7901, 'NAICS', 1080, 42492, 4, 1079, 424920, 5),
(7902, 'NAICS', 1726, 561, 2, 1786, 561910, 5),
(7903, 'SEC', 2418, 3560, 3, 2419, 3561, 4),
(7904, 'NAICS', 1554, 525, 2, 1567, 525990, 5),
(7905, 'NAICS', 2136, 921, 2, 2139, 92111, 4),
(7906, 'SIC', 3576, 3900, 2, 3584, 3942, 4),
(7907, 'NAICS', 1536, 524, 2, 1553, 524298, 5),
(7908, 'SIC', 2826, 210, 3, 2829, 213, 4),
(7909, 'SIC', 4308, 20, 1, 3124, 2400, 2),
(7910, 'SIC', 2982, 2000, 2, 3006, 2047, 4),
(7911, 'SIC', 4310, 50, 1, 3782, 5148, 4),
(7912, 'NAICS', 1853, 62111, 4, 1854, 621111, 5),
(7913, 'SIC', 4308, 20, 1, 3282, 3100, 2),
(7914, 'NAICS', 930, 42, 1, 1023, 4242, 3),
(7915, 'SEC', 2319, 2800, 2, 2321, 2820, 3),
(7916, 'SIC', 2982, 2000, 2, 3013, 2061, 4),
(7917, 'SEC', 2608, 5270, 3, 2609, 5271, 4),
(7918, 'SEC', 2319, 2800, 2, 2332, 2851, 4),
(7919, 'SIC', 4305, 1, 1, 2857, 742, 4),
(7920, 'SEC', 2792, 40, 1, 2515, 4013, 4),
(7921, 'SIC', 3419, 3500, 2, 3429, 3533, 4),
(7922, 'NAICS', 109, 1141, 3, 111, 114111, 5),
(7923, 'SIC', 3444, 3550, 3, 3446, 3553, 4),
(7924, 'NAICS', 1792, 562, 2, 1794, 56211, 4),
(7925, 'SIC', 3626, 4220, 3, 3628, 4222, 4),
(7926, 'NAICS', 1402, 51, 1, 1428, 51219, 4),
(7927, 'NAICS', 156, 2123, 3, 169, 212392, 5),
(7928, 'SIC', 4305, 1, 1, 2865, 781, 4),
(7929, 'NAICS', 19, 1112, 3, 22, 111219, 5),
(7930, 'NAICS', 932, 4231, 3, 936, 42312, 4),
(7931, 'SEC', 2235, 1620, 3, 2236, 1623, 4),
(7932, 'SIC', 3461, 3570, 3, 3467, 3579, 4),
(7933, 'SIC', 3958, 6300, 2, 3970, 6370, 3),
(7934, 'NAICS', 16, 11119, 4, 18, 111199, 5),
(7935, 'SEC', 2434, 3600, 2, 2443, 3650, 3),
(7936, 'SIC', 3958, 6300, 2, 3969, 6361, 4),
(7937, 'NAICS', 2031, 7225, 3, 2035, 722514, 5),
(7938, 'SIC', 3214, 2800, 2, 3216, 2812, 4),
(7939, 'SIC', 3371, 3400, 2, 3392, 3450, 3),
(7940, 'SIC', 4308, 20, 1, 3436, 3542, 4),
(7941, 'SIC', 2847, 700, 2, 2855, 740, 3),
(7942, 'NAICS', 931, 423, 2, 1000, 423850, 5),
(7943, 'SIC', 3033, 2090, 3, 3037, 2096, 4),
(7944, 'NAICS', 1437, 51223, 4, 1436, 512230, 5),
(7945, 'NAICS', 2071, 812, 2, 2078, 812191, 5),
(7946, 'SIC', 3977, 6500, 2, 3984, 6519, 4),
(7947, 'NAICS', 2071, 812, 2, 2082, 81221, 4),
(7948, 'SIC', 3693, 4900, 2, 3703, 4932, 4),
(7949, 'NAICS', 1480, 52, 1, 1527, 523910, 5),
(7950, 'NAICS', 1569, 53, 1, 1601, 532220, 5),
(7951, 'NAICS', 180, 22, 1, 186, 221113, 5),
(7952, 'NAICS', 930, 42, 1, 965, 42345, 4),
(7953, 'NAICS', 930, 42, 1, 1087, 424990, 5),
(7954, 'SEC', 2791, 20, 1, 2471, 3743, 4),
(7955, 'NAICS', 955, 4234, 3, 959, 42342, 4),
(7956, 'NAICS', 1444, 51511, 4, 1446, 515112, 5),
(7957, 'SIC', 4308, 20, 1, 2983, 2010, 3),
(7958, 'NAICS', 98, 113, 2, 106, 113310, 5),
(7959, 'SIC', 3774, 5140, 3, 3775, 5141, 4),
(7960, 'SEC', 2794, 52, 1, 2608, 5270, 3),
(7961, 'NAICS', 1725, 56, 1, 1763, 56159, 4),
(7962, 'SIC', 2798, 100, 2, 2802, 115, 4),
(7963, 'NAICS', 132, 21, 1, 155, 212299, 5),
(7964, 'SEC', 2795, 60, 1, 2660, 6110, 3),
(7965, 'NAICS', 2188, 926, 2, 2197, 92614, 4),
(7966, 'SEC', 2633, 5730, 3, 2635, 5734, 4),
(7967, 'SIC', 4308, 20, 1, 3132, 2431, 4),
(7968, 'SIC', 4040, 7300, 2, 4071, 7376, 4),
(7969, 'NAICS', 1, 11, 1, 46, 111920, 5),
(7970, 'SIC', 4313, 70, 1, 4202, 8399, 4),
(7971, 'SEC', 2791, 20, 1, 2493, 3845, 4),
(7972, 'SIC', 4308, 20, 1, 3118, 2393, 4),
(7973, 'NAICS', 89, 1129, 3, 92, 112920, 5),
(7974, 'NAICS', 1054, 4245, 3, 1056, 42451, 4),
(7975, 'NAICS', 1492, 52213, 4, 1491, 522130, 5),
(7976, 'SIC', 3230, 2840, 3, 3234, 2844, 4),
(7977, 'SIC', 4310, 50, 1, 3715, 5000, 2),
(7978, 'SIC', 3797, 5190, 3, 3800, 5193, 4),
(7979, 'NAICS', 1480, 52, 1, 1490, 52212, 4),
(7980, 'NAICS', 1691, 54181, 4, 1690, 541810, 5),
(7981, 'SIC', 3190, 2700, 2, 3193, 2720, 3),
(7982, 'NAICS', 85, 11251, 4, 88, 112519, 5),
(7983, 'SIC', 3948, 6200, 2, 3956, 6282, 4),
(7984, 'SIC', 3073, 2280, 3, 3075, 2282, 4),
(7985, 'SIC', 4309, 40, 1, 3681, 4810, 3),
(7986, 'SIC', 4075, 7380, 3, 4079, 7384, 4),
(7987, 'NAICS', 930, 42, 1, 1074, 424820, 5),
(7988, 'SIC', 4308, 20, 1, 3393, 3451, 4),
(7989, 'SIC', 3211, 2790, 3, 3213, 2796, 4),
(7990, 'NAICS', 1480, 52, 1, 1512, 52239, 4),
(7991, 'NAICS', 1, 11, 1, 73, 112330, 5),
(7992, 'SIC', 4305, 1, 1, 2810, 139, 4),
(7993, 'NAICS', 1850, 62, 1, 1901, 6223, 3),
(7994, 'SIC', 3869, 5700, 2, 3880, 5735, 4),
(7995, 'SIC', 4306, 10, 1, 2905, 1230, 3),
(7996, 'NAICS', 89, 1129, 3, 95, 11293, 4),
(7997, 'SIC', 4305, 1, 1, 2867, 783, 4),
(7998, 'SIC', 3680, 4800, 2, 3683, 4813, 4),
(7999, 'SIC', 3715, 5000, 2, 3748, 5078, 4),
(8000, 'NAICS', 1, 11, 1, 101, 11311, 4),
(8001, 'SIC', 4313, 70, 1, 4143, 7996, 4),
(8002, 'NAICS', 1812, 61, 1, 1823, 6114, 3),
(8003, 'SIC', 3480, 3600, 2, 3525, 3699, 4),
(8004, 'SIC', 3426, 3530, 3, 3430, 3534, 4),
(8005, 'NAICS', 991, 4238, 3, 1001, 42385, 4),
(8006, 'NAICS', 1514, 5231, 3, 1520, 52313, 4),
(8007, 'NAICS', 2071, 812, 2, 2079, 812199, 5),
(8008, 'SEC', 2356, 3210, 3, 2357, 3211, 4),
(8009, 'NAICS', 1812, 61, 1, 1837, 611610, 5),
(8010, 'NAICS', 180, 22, 1, 193, 221121, 5),
(8011, 'NAICS', 2, 111, 2, 31, 111333, 5),
(8012, 'SEC', 2793, 50, 1, 2569, 5010, 3),
(8013, 'SIC', 3955, 6280, 3, 3956, 6282, 4),
(8014, 'NAICS', 218, 237, 2, 229, 2373, 3),
(8015, 'NAICS', 1726, 561, 2, 1788, 561920, 5),
(8016, 'NAICS', 1813, 611, 2, 1847, 6117, 3),
(8017, 'SIC', 4149, 8020, 3, 4150, 8021, 4),
(8018, 'SEC', 2240, 2000, 2, 2247, 2030, 3),
(8019, 'NAICS', 1966, 7115, 3, 1967, 711510, 5),
(8020, 'NAICS', 1625, 541, 2, 1684, 54171, 4),
(8021, 'SIC', 3077, 2290, 3, 3081, 2298, 4),
(8022, 'SEC', 2659, 6100, 2, 2669, 6163, 4),
(8023, 'SIC', 2902, 1220, 3, 2903, 1221, 4),
(8024, 'NAICS', 1813, 611, 2, 1829, 61143, 4),
(8025, 'SIC', 4311, 52, 1, 3916, 5999, 4),
(8026, 'SEC', 2791, 20, 1, 2331, 2850, 3),
(8027, 'SIC', 3282, 3100, 2, 3290, 3144, 4),
(8028, 'SIC', 4113, 7800, 2, 4117, 7820, 3),
(8029, 'NAICS', 205, 23, 1, 256, 238220, 5),
(8030, 'SIC', 3337, 3300, 2, 3360, 3356, 4),
(8031, 'SIC', 3044, 2120, 3, 3045, 2121, 4),
(8032, 'SIC', 3762, 5100, 2, 3794, 5180, 3),
(8033, 'NAICS', 1695, 54183, 4, 1694, 541830, 5),
(8034, 'NAICS', 2037, 81, 1, 2076, 812113, 5),
(8035, 'NAICS', 1442, 515, 2, 1445, 515111, 5),
(8036, 'NAICS', 1588, 53132, 4, 1587, 531320, 5),
(8037, 'SEC', 2790, 15, 1, 2236, 1623, 4),
(8038, 'SEC', 2791, 20, 1, 2484, 3825, 4),
(8039, 'SEC', 2368, 3280, 3, 2369, 3281, 4),
(8040, 'SIC', 3124, 2400, 2, 3145, 2491, 4),
(8041, 'NAICS', 1, 11, 1, 119, 11511, 4),
(8042, 'NAICS', 213, 2362, 3, 215, 23621, 4),
(8043, 'NAICS', 2004, 721, 2, 2009, 72112, 4),
(8044, 'SIC', 2858, 750, 3, 2859, 751, 4),
(8045, 'NAICS', 260, 2383, 3, 272, 23839, 4),
(8046, 'NAICS', 1943, 711, 2, 1965, 71141, 4),
(8047, 'SIC', 3000, 2040, 3, 3004, 2045, 4),
(8048, 'NAICS', 974, 42352, 4, 973, 423520, 5),
(8049, 'SEC', 2434, 3600, 2, 2440, 3630, 3),
(8050, 'SIC', 3978, 6510, 3, 3979, 6512, 4),
(8051, 'NAICS', 205, 23, 1, 250, 23817, 4),
(8052, 'SIC', 3050, 2200, 2, 3074, 2281, 4),
(8053, 'SIC', 4306, 10, 1, 2915, 1381, 4),
(8054, 'SIC', 4305, 1, 1, 2878, 913, 4),
(8055, 'NAICS', 198, 2213, 3, 200, 22131, 4),
(8056, 'NAICS', 1733, 5613, 3, 1737, 561320, 5),
(8057, 'SIC', 4308, 20, 1, 3193, 2720, 3),
(8058, 'SEC', 2793, 50, 1, 2578, 5051, 4),
(8059, 'NAICS', 1701, 54186, 4, 1700, 541860, 5),
(8060, 'SEC', 2240, 2000, 2, 2254, 2080, 3),
(8061, 'SEC', 2793, 50, 1, 2596, 5140, 3),
(8062, 'NAICS', 1624, 54, 1, 1644, 54132, 4),
(8063, 'SIC', 3103, 2360, 3, 3105, 2369, 4),
(8064, 'SIC', 4310, 50, 1, 3793, 5172, 4),
(8065, 'SEC', 2796, 70, 1, 2748, 7900, 2),
(8066, 'SEC', 2796, 70, 1, 2710, 7010, 3),
(8067, 'NAICS', 1888, 6219, 3, 1890, 62191, 4),
(8068, 'NAICS', 56, 112, 2, 67, 11221, 4),
(8069, 'NAICS', 955, 4234, 3, 967, 42346, 4),
(8070, 'NAICS', 205, 23, 1, 216, 236220, 5),
(8071, 'SIC', 2955, 1700, 2, 2962, 1740, 3),
(8072, 'SIC', 4007, 7000, 2, 4016, 7041, 4),
(8073, 'SIC', 2884, 1000, 2, 2889, 1030, 3),
(8074, 'SIC', 3261, 3000, 2, 3266, 3050, 3),
(8075, 'NAICS', 235, 238, 2, 270, 23835, 4),
(8076, 'SIC', 4308, 20, 1, 3157, 2521, 4),
(8077, 'NAICS', 181, 221, 2, 195, 2212, 3),
(8078, 'NAICS', 2151, 9221, 3, 2164, 922190, 5),
(8079, 'NAICS', 1486, 5221, 3, 1494, 52219, 4),
(8080, 'SIC', 4308, 20, 1, 3541, 3743, 4),
(8081, 'SIC', 3148, 2500, 2, 3158, 2522, 4),
(8082, 'SIC', 3419, 3500, 2, 3433, 3537, 4),
(8083, 'SIC', 4313, 70, 1, 4124, 7841, 4),
(8084, 'SIC', 3977, 6500, 2, 3980, 6513, 4),
(8085, 'SEC', 4336, 99, 1, 4338, 8888, 2),
(8086, 'SIC', 3282, 3100, 2, 3285, 3130, 3),
(8087, 'SEC', 2791, 20, 1, 2483, 3824, 4),
(8088, 'SEC', 2795, 60, 1, 2655, 6035, 4),
(8089, 'SEC', 2659, 6100, 2, 2663, 6141, 4),
(8090, 'SIC', 4100, 7600, 2, 4111, 7694, 4),
(8091, 'NAICS', 1721, 55111, 4, 1723, 551112, 5),
(8092, 'NAICS', 1726, 561, 2, 1775, 561710, 5),
(8093, 'NAICS', 930, 42, 1, 1014, 42399, 4),
(8094, 'SEC', 2792, 40, 1, 2527, 4510, 3),
(8095, 'SEC', 2793, 50, 1, 2601, 5171, 4),
(8096, 'SIC', 3083, 2300, 2, 3110, 2384, 4),
(8097, 'NAICS', 1943, 711, 2, 1962, 71132, 4),
(8098, 'SIC', 4313, 70, 1, 4022, 7215, 4),
(8099, 'SIC', 4307, 15, 1, 2957, 1711, 4),
(8100, 'NAICS', 1851, 621, 2, 1889, 621910, 5),
(8101, 'NAICS', 1850, 62, 1, 1893, 621999, 5),
(8102, 'SEC', 2791, 20, 1, 2327, 2836, 4),
(8103, 'SIC', 3083, 2300, 2, 3112, 2386, 4),
(8104, 'NAICS', 1520, 52313, 4, 1519, 523130, 5),
(8105, 'SEC', 2505, 3940, 3, 2507, 3944, 4),
(8106, 'SEC', 2791, 20, 1, 2358, 3220, 3),
(8107, 'NAICS', 132, 21, 1, 154, 212291, 5),
(8108, 'NAICS', 205, 23, 1, 209, 236115, 5),
(8109, 'NAICS', 2093, 8129, 3, 2102, 81299, 4),
(8110, 'SEC', 2403, 3500, 2, 2418, 3560, 3),
(8111, 'SIC', 4311, 52, 1, 3814, 5271, 4),
(8112, 'SIC', 4308, 20, 1, 3475, 3592, 4),
(8113, 'SIC', 4313, 70, 1, 4140, 7991, 4),
(8114, 'NAICS', 1963, 7114, 3, 1964, 711410, 5),
(8115, 'SEC', 2472, 3750, 3, 2473, 3751, 4),
(8116, 'NAICS', 1514, 5231, 3, 1515, 523110, 5),
(8117, 'SIC', 3794, 5180, 3, 3795, 5181, 4),
(8118, 'NAICS', 1061, 4246, 3, 1062, 424610, 5),
(8119, 'NAICS', 1813, 611, 2, 1836, 6116, 3),
(8120, 'NAICS', 1851, 621, 2, 1858, 62121, 4),
(8121, 'SIC', 4065, 7370, 3, 4071, 7376, 4),
(8122, 'NAICS', 1667, 54151, 4, 1670, 541513, 5),
(8123, 'NAICS', 205, 23, 1, 277, 23899, 4),
(8124, 'SEC', 2796, 70, 1, 2763, 8082, 4),
(8125, 'NAICS', 1, 11, 1, 85, 11251, 4),
(8126, 'NAICS', 1480, 52, 1, 1506, 5223, 3),
(8127, 'NAICS', 1725, 56, 1, 1761, 561520, 5),
(8128, 'NAICS', 2020, 722, 2, 2036, 722515, 5),
(8129, 'SIC', 4308, 20, 1, 3342, 3316, 4),
(8130, 'NAICS', 1402, 51, 1, 1469, 51821, 4),
(8131, 'NAICS', 1683, 5417, 3, 1687, 541720, 5),
(8132, 'NAICS', 2167, 9231, 3, 2173, 92313, 4),
(8133, 'NAICS', 932, 4231, 3, 933, 423110, 5),
(8134, 'NAICS', 1799, 56221, 4, 1801, 562212, 5),
(8135, 'NAICS', 1726, 561, 2, 1762, 56152, 4),
(8136, 'SIC', 4308, 20, 1, 3070, 2269, 4),
(8137, 'SIC', 4313, 70, 1, 4194, 8322, 4),
(8138, 'SEC', 2796, 70, 1, 2722, 7360, 3),
(8139, 'NAICS', 1419, 512, 2, 1441, 51229, 4),
(8140, 'NAICS', 68, 1123, 3, 74, 11233, 4),
(8141, 'NAICS', 181, 221, 2, 197, 22121, 4),
(8142, 'SEC', 2791, 20, 1, 2489, 3841, 4),
(8143, 'SIC', 4314, 90, 1, 4299, 9711, 4),
(8144, 'SIC', 4306, 10, 1, 2926, 1442, 4),
(8145, 'NAICS', 2037, 81, 1, 2116, 813319, 5),
(8146, 'SEC', 2796, 70, 1, 2770, 8300, 2),
(8147, 'SIC', 3552, 3800, 2, 3563, 3829, 4),
(8148, 'SIC', 4308, 20, 1, 3553, 3810, 3),
(8149, 'NAICS', 132, 21, 1, 169, 212392, 5),
(8150, 'NAICS', 1466, 518, 2, 1469, 51821, 4),
(8151, 'NAICS', 1705, 54189, 4, 1704, 541890, 5),
(8152, 'SIC', 4146, 8000, 2, 4172, 8092, 4),
(8153, 'SEC', 2796, 70, 1, 2751, 7990, 3),
(8154, 'NAICS', 56, 112, 2, 58, 11211, 4),
(8155, 'NAICS', 2135, 92, 1, 2147, 92115, 4),
(8156, 'SIC', 3127, 2420, 3, 3128, 2421, 4),
(8157, 'NAICS', 1812, 61, 1, 1844, 611691, 5),
(8158, 'NAICS', 1813, 611, 2, 1835, 611519, 5),
(8159, 'SIC', 4308, 20, 1, 3589, 3952, 4),
(8160, 'SIC', 4308, 20, 1, 3463, 3572, 4),
(8161, 'NAICS', 1673, 54161, 4, 1676, 541613, 5),
(8162, 'SEC', 2791, 20, 1, 2509, 3950, 3),
(8163, 'SIC', 4125, 7900, 2, 4132, 7933, 4),
(8164, 'SIC', 4308, 20, 1, 3450, 3559, 4),
(8165, 'NAICS', 930, 42, 1, 1052, 424490, 5),
(8166, 'NAICS', 1719, 551, 2, 1724, 551114, 5),
(8167, 'SEC', 2319, 2800, 2, 2335, 2890, 3),
(8168, 'NAICS', 205, 23, 1, 226, 2372, 3),
(8169, 'NAICS', 1908, 6232, 3, 1911, 623220, 5),
(8170, 'NAICS', 2073, 81211, 4, 2075, 812112, 5),
(8171, 'SIC', 3966, 6350, 3, 3967, 6351, 4),
(8172, 'NAICS', 1071, 4248, 3, 1073, 42481, 4),
(8173, 'SIC', 3576, 3900, 2, 3599, 3996, 4),
(8174, 'SIC', 3368, 3390, 3, 3369, 3398, 4),
(8175, 'NAICS', 1624, 54, 1, 1632, 541191, 5),
(8176, 'NAICS', 1480, 52, 1, 1533, 52399, 4),
(8177, 'NAICS', 1942, 71, 1, 1946, 71111, 4),
(8178, 'SEC', 2795, 60, 1, 2664, 6150, 3),
(8179, 'SIC', 3362, 3360, 3, 3366, 3366, 4),
(8180, 'SIC', 3489, 3630, 3, 3490, 3631, 4),
(8181, 'NAICS', 1403, 511, 2, 1418, 51121, 4),
(8182, 'NAICS', 235, 238, 2, 261, 238310, 5),
(8183, 'SIC', 4309, 40, 1, 3709, 4953, 4),
(8184, 'SEC', 2384, 3400, 2, 2388, 3420, 3),
(8185, 'NAICS', 1, 11, 1, 34, 111336, 5),
(8186, 'SEC', 2450, 3670, 3, 2451, 3672, 4),
(8187, 'NAICS', 1624, 54, 1, 1647, 541340, 5),
(8188, 'NAICS', 1851, 621, 2, 1871, 6214, 3),
(8189, 'SIC', 4313, 70, 1, 4009, 7011, 4),
(8190, 'SIC', 2832, 240, 3, 2833, 241, 4),
(8191, 'SEC', 2371, 3300, 2, 2376, 3330, 3),
(8192, 'NAICS', 1625, 541, 2, 1677, 541614, 5),
(8193, 'SIC', 4117, 7820, 3, 4119, 7829, 4),
(8194, 'NAICS', 1831, 61151, 4, 1832, 611511, 5),
(8195, 'NAICS', 2071, 812, 2, 2084, 81222, 4),
(8196, 'NAICS', 1, 11, 1, 18, 111199, 5),
(8197, 'NAICS', 260, 2383, 3, 262, 23831, 4),
(8198, 'NAICS', 2, 111, 2, 25, 11131, 4),
(8199, 'NAICS', 1092, 42511, 4, 1091, 425110, 5),
(8200, 'SEC', 2349, 3080, 3, 2351, 3086, 4),
(8201, 'SEC', 2795, 60, 1, 2651, 6021, 4),
(8202, 'SIC', 2884, 1000, 2, 2899, 1094, 4),
(8203, 'SIC', 3033, 2090, 3, 3040, 2099, 4),
(8204, 'SIC', 2921, 1420, 3, 2922, 1422, 4),
(8205, 'SIC', 4308, 20, 1, 3478, 3596, 4),
(8206, 'SIC', 4162, 8060, 3, 4164, 8063, 4),
(8207, 'SIC', 4297, 9700, 2, 4298, 9710, 3),
(8208, 'NAICS', 2037, 81, 1, 2061, 8114, 3),
(8209, 'NAICS', 2039, 8111, 3, 2051, 811198, 5),
(8210, 'NAICS', 2135, 92, 1, 2187, 92512, 4),
(8211, 'NAICS', 982, 4237, 3, 985, 423720, 5),
(8212, 'NAICS', 1015, 424, 2, 1081, 424930, 5),
(8213, 'SIC', 4308, 20, 1, 3402, 3471, 4),
(8214, 'NAICS', 56, 112, 2, 80, 112410, 5),
(8215, 'SIC', 4313, 70, 1, 4024, 7217, 4),
(8216, 'SIC', 4309, 40, 1, 3692, 4899, 4),
(8217, 'SEC', 2796, 70, 1, 2782, 8742, 4),
(8218, 'SEC', 2323, 2830, 3, 2326, 2835, 4),
(8219, 'NAICS', 1526, 5239, 3, 1530, 52392, 4),
(8220, 'SIC', 4285, 9610, 3, 4286, 9611, 4),
(8221, 'NAICS', 1451, 51521, 4, 1450, 515210, 5),
(8222, 'NAICS', 2188, 926, 2, 2194, 926130, 5),
(8223, 'SIC', 3261, 3000, 2, 3274, 3082, 4),
(8224, 'SEC', 2435, 3610, 3, 2436, 3612, 4),
(8225, 'SIC', 4308, 20, 1, 3326, 3274, 4),
(8226, 'NAICS', 2071, 812, 2, 2092, 812332, 5),
(8227, 'NAICS', 132, 21, 1, 156, 2123, 3),
(8228, 'SIC', 3167, 2600, 2, 3178, 2656, 4),
(8229, 'SIC', 4310, 50, 1, 3795, 5181, 4),
(8230, 'NAICS', 1076, 4249, 3, 1079, 424920, 5),
(8231, 'NAICS', 1851, 621, 2, 1874, 621420, 5),
(8232, 'NAICS', 1813, 611, 2, 1848, 611710, 5),
(8233, 'SIC', 3083, 2300, 2, 3091, 2326, 4),
(8234, 'NAICS', 84, 1125, 3, 87, 112512, 5),
(8235, 'NAICS', 1814, 6111, 3, 1815, 611110, 5),
(8236, 'NAICS', 1500, 52229, 4, 1502, 522292, 5),
(8237, 'SIC', 4311, 52, 1, 3822, 5400, 2),
(8238, 'NAICS', 1625, 541, 2, 1713, 54193, 4),
(8239, 'SEC', 2792, 40, 1, 2535, 4610, 3),
(8240, 'SEC', 2630, 5700, 2, 2631, 5710, 3),
(8241, 'NAICS', 138, 212, 2, 150, 21223, 4),
(8242, 'SIC', 4313, 70, 1, 4141, 7992, 4),
(8243, 'NAICS', 1741, 5614, 3, 1744, 56142, 4),
(8244, 'SIC', 4313, 70, 1, 4103, 7623, 4),
(8245, 'NAICS', 36, 1114, 3, 39, 111419, 5),
(8246, 'NAICS', 930, 42, 1, 983, 423710, 5),
(8247, 'SIC', 3337, 3300, 2, 3353, 3340, 3),
(8248, 'SIC', 4223, 8700, 2, 4234, 8734, 4),
(8249, 'SIC', 4313, 70, 1, 4225, 8711, 4),
(8250, 'NAICS', 2073, 81211, 4, 2074, 812111, 5),
(8251, 'SIC', 4308, 20, 1, 3262, 3010, 3),
(8252, 'NAICS', 2093, 8129, 3, 2094, 812910, 5),
(8253, 'SIC', 4308, 20, 1, 3533, 3720, 3),
(8254, 'SIC', 4313, 70, 1, 4026, 7219, 4),
(8255, 'SIC', 3338, 3310, 3, 3342, 3316, 4),
(8256, 'SEC', 2791, 20, 1, 2244, 2015, 4),
(8257, 'SEC', 2791, 20, 1, 2418, 3560, 3),
(8258, 'SIC', 4312, 60, 1, 3931, 6080, 3),
(8259, 'SEC', 2646, 5960, 3, 2647, 5961, 4),
(8260, 'SIC', 2798, 100, 2, 2813, 170, 3),
(8261, 'NAICS', 206, 236, 2, 207, 2361, 3),
(8262, 'NAICS', 235, 238, 2, 253, 2382, 3),
(8263, 'SIC', 4146, 8000, 2, 4154, 8041, 4),
(8264, 'NAICS', 1, 11, 1, 66, 112210, 5),
(8265, 'SIC', 3917, 6000, 2, 3922, 6021, 4),
(8266, 'SIC', 3115, 2390, 3, 3121, 2396, 4),
(8267, 'SIC', 4313, 70, 1, 4199, 8360, 3),
(8268, 'NAICS', 1026, 4243, 3, 1027, 424310, 5),
(8269, 'SIC', 3822, 5400, 2, 3826, 5421, 4),
(8270, 'SEC', 2384, 3400, 2, 2398, 3452, 4),
(8271, 'SEC', 2623, 5600, 2, 2626, 5650, 3),
(8272, 'SEC', 2695, 6510, 3, 2696, 6512, 4),
(8273, 'NAICS', 28, 11133, 4, 32, 111334, 5),
(8274, 'NAICS', 205, 23, 1, 230, 237310, 5),
(8275, 'NAICS', 2037, 81, 1, 2121, 813910, 5),
(8276, 'NAICS', 1, 11, 1, 52, 11199, 4),
(8277, 'NAICS', 930, 42, 1, 1047, 42446, 4),
(8278, 'SIC', 4313, 70, 1, 4069, 7374, 4),
(8279, 'SIC', 4307, 15, 1, 2947, 1542, 4),
(8280, 'SIC', 3564, 3840, 3, 3567, 3843, 4),
(8281, 'NAICS', 1624, 54, 1, 1698, 541850, 5),
(8282, 'SIC', 4313, 70, 1, 4116, 7819, 4),
(8283, 'SEC', 2754, 8010, 3, 2755, 8011, 4),
(8284, 'SIC', 4308, 20, 1, 3452, 3561, 4),
(8285, 'SIC', 4308, 20, 1, 3254, 2911, 4),
(8286, 'SEC', 2307, 2730, 3, 2308, 2731, 4),
(8287, 'SIC', 4206, 8420, 3, 4207, 8422, 4),
(8288, 'SIC', 4219, 8660, 3, 4220, 8661, 4),
(8289, 'NAICS', 2037, 81, 1, 2112, 8133, 3),
(8290, 'SIC', 4305, 1, 1, 2820, 180, 3),
(8291, 'NAICS', 1591, 532, 2, 1593, 53211, 4),
(8292, 'SEC', 2791, 20, 1, 2264, 2211, 4),
(8293, 'SEC', 2637, 5800, 2, 2639, 5812, 4),
(8294, 'NAICS', 2107, 8132, 3, 2108, 81321, 4),
(8295, 'SEC', 2503, 3930, 3, 2504, 3931, 4),
(8296, 'NAICS', 1402, 51, 1, 1460, 517410, 5),
(8297, 'SIC', 4248, 9110, 3, 4249, 9111, 4),
(8298, 'NAICS', 1890, 62191, 4, 1889, 621910, 5),
(8299, 'NAICS', 2085, 8123, 3, 2086, 812310, 5),
(8300, 'SEC', 2624, 5620, 3, 2625, 5621, 4),
(8301, 'NAICS', 23, 1113, 3, 34, 111336, 5),
(8302, 'SEC', 2321, 2820, 3, 2322, 2821, 4),
(8303, 'NAICS', 1850, 62, 1, 1875, 62142, 4),
(8304, 'NAICS', 56, 112, 2, 94, 112930, 5),
(8305, 'NAICS', 1726, 561, 2, 1773, 561622, 5),
(8306, 'NAICS', 1836, 6116, 3, 1841, 611630, 5),
(8307, 'SIC', 3694, 4910, 3, 3695, 4911, 4),
(8308, 'SIC', 3595, 3990, 3, 3599, 3996, 4),
(8309, 'NAICS', 2150, 922, 2, 2161, 92215, 4),
(8310, 'NAICS', 1625, 541, 2, 1670, 541513, 5),
(8311, 'SIC', 4307, 15, 1, 2973, 1780, 3),
(8312, 'SIC', 3605, 4100, 2, 3610, 4121, 4),
(8313, 'SIC', 3715, 5000, 2, 3717, 5012, 4),
(8314, 'NAICS', 932, 4231, 3, 934, 42311, 4),
(8315, 'SIC', 2939, 1500, 2, 2941, 1521, 4),
(8316, 'SIC', 2868, 800, 2, 2870, 811, 4),
(8317, 'SIC', 4308, 20, 1, 3434, 3540, 3),
(8318, 'SIC', 3337, 3300, 2, 3347, 3324, 4),
(8319, 'SIC', 4311, 52, 1, 3897, 5944, 4),
(8320, 'SIC', 3371, 3400, 2, 3405, 3482, 4),
(8321, 'SIC', 3214, 2800, 2, 3248, 2892, 4),
(8322, 'SIC', 3083, 2300, 2, 3089, 2323, 4),
(8323, 'SIC', 3198, 2740, 3, 3199, 2741, 4),
(8324, 'NAICS', 132, 21, 1, 138, 212, 2),
(8325, 'SEC', 2764, 8090, 3, 2765, 8093, 4),
(8326, 'SIC', 3605, 4100, 2, 3607, 4111, 4),
(8327, 'SIC', 3822, 5400, 2, 3832, 5451, 4),
(8328, 'SIC', 4312, 60, 1, 3956, 6282, 4),
(8329, 'NAICS', 931, 423, 2, 979, 42362, 4),
(8330, 'NAICS', 1480, 52, 1, 1489, 522120, 5),
(8331, 'NAICS', 181, 221, 2, 204, 22133, 4),
(8332, 'NAICS', 2136, 921, 2, 2144, 921140, 5),
(8333, 'SEC', 2795, 60, 1, 2682, 6324, 4),
(8334, 'SEC', 2384, 3400, 2, 2401, 3480, 3),
(8335, 'NAICS', 1, 11, 1, 39, 111419, 5),
(8336, 'SEC', 2793, 50, 1, 2568, 5000, 2),
(8337, 'NAICS', 931, 423, 2, 958, 423420, 5),
(8338, 'NAICS', 1931, 62422, 4, 1932, 624221, 5),
(8339, 'SIC', 4309, 40, 1, 3602, 4010, 3),
(8340, 'NAICS', 1015, 424, 2, 1078, 42491, 4),
(8341, 'NAICS', 1536, 524, 2, 1543, 524127, 5),
(8342, 'SIC', 3715, 5000, 2, 3742, 5064, 4),
(8343, 'SIC', 3083, 2300, 2, 3109, 2381, 4),
(8344, 'SEC', 2338, 2910, 3, 2339, 2911, 4),
(8345, 'NAICS', 147, 21222, 4, 148, 212221, 5),
(8346, 'NAICS', 1076, 4249, 3, 1082, 42493, 4),
(8347, 'SEC', 2623, 5600, 2, 2624, 5620, 3),
(8348, 'SEC', 2794, 52, 1, 2612, 5311, 4),
(8349, 'SIC', 4308, 20, 1, 3509, 3663, 4),
(8350, 'NAICS', 2080, 8122, 3, 2081, 812210, 5),
(8351, 'SIC', 3977, 6500, 2, 3988, 6541, 4),
(8352, 'NAICS', 131, 11531, 4, 130, 115310, 5),
(8353, 'SIC', 3958, 6300, 2, 3960, 6311, 4),
(8354, 'SIC', 3371, 3400, 2, 3374, 3412, 4),
(8355, 'SIC', 4308, 20, 1, 3351, 3334, 4),
(8356, 'NAICS', 13, 11115, 4, 12, 111150, 5),
(8357, 'SEC', 2791, 20, 1, 2419, 3561, 4),
(8358, 'SEC', 2766, 8100, 2, 2768, 8111, 4),
(8359, 'SIC', 4314, 90, 1, 4247, 9100, 2),
(8360, 'SIC', 3050, 2200, 2, 3053, 2220, 3),
(8361, 'SIC', 3867, 5690, 3, 3868, 5699, 4),
(8362, 'NAICS', 2037, 81, 1, 2122, 81391, 4),
(8363, 'SIC', 3484, 3620, 3, 3485, 3621, 4),
(8364, 'SIC', 3804, 5200, 2, 3811, 5260, 3),
(8365, 'SIC', 3961, 6320, 3, 3962, 6321, 4),
(8366, 'SIC', 4313, 70, 1, 4076, 7381, 4),
(8367, 'NAICS', 84, 1125, 3, 86, 112511, 5),
(8368, 'NAICS', 1569, 53, 1, 1595, 532112, 5),
(8369, 'NAICS', 1449, 5152, 3, 1450, 515210, 5),
(8370, 'NAICS', 1541, 52412, 4, 1542, 524126, 5),
(8371, 'NAICS', 1719, 551, 2, 1722, 551111, 5),
(8372, 'SIC', 4146, 8000, 2, 4149, 8020, 3),
(8373, 'NAICS', 2071, 812, 2, 2091, 812331, 5),
(8374, 'SIC', 3762, 5100, 2, 3803, 5199, 4),
(8375, 'NAICS', 2037, 81, 1, 2133, 814110, 5),
(8376, 'SIC', 3992, 6700, 2, 4002, 6790, 3),
(8377, 'SIC', 4139, 7990, 3, 4141, 7992, 4),
(8378, 'SEC', 2791, 20, 1, 2405, 3520, 3),
(8379, 'SEC', 2302, 2700, 2, 2310, 2740, 3),
(8380, 'SIC', 2982, 2000, 2, 2998, 2037, 4),
(8381, 'SEC', 2791, 20, 1, 2422, 3567, 4),
(8382, 'SIC', 4208, 8600, 2, 4219, 8660, 3),
(8383, 'NAICS', 2037, 81, 1, 2118, 813410, 5),
(8384, 'SEC', 2552, 4900, 2, 2560, 4931, 4),
(8385, 'NAICS', 2019, 72131, 4, 2018, 721310, 5),
(8386, 'SIC', 3480, 3600, 2, 3484, 3620, 3),
(8387, 'SEC', 2521, 4230, 3, 2522, 4231, 4),
(8388, 'SIC', 3823, 5410, 3, 3824, 5411, 4),
(8389, 'SIC', 2951, 1620, 3, 2953, 1623, 4),
(8390, 'SEC', 2795, 60, 1, 4322, 6180, 3),
(8391, 'NAICS', 1480, 52, 1, 1522, 52314, 4),
(8392, 'SIC', 3349, 3330, 3, 3350, 3331, 4),
(8393, 'SIC', 4308, 20, 1, 3195, 2730, 3),
(8394, 'SEC', 2792, 40, 1, 2531, 4522, 4),
(8395, 'SEC', 2793, 50, 1, 2591, 5100, 2),
(8396, 'SIC', 3149, 2510, 3, 3152, 2514, 4),
(8397, 'NAICS', 1943, 711, 2, 1953, 7112, 3),
(8398, 'NAICS', 1894, 622, 2, 1898, 6222, 3),
(8399, 'SIC', 4308, 20, 1, 2987, 2020, 3),
(8400, 'SIC', 4040, 7300, 2, 4061, 7359, 4),
(8401, 'NAICS', 2135, 92, 1, 2145, 92114, 4),
(8402, 'SIC', 3269, 3060, 3, 3270, 3061, 4),
(8403, 'NAICS', 2151, 9221, 3, 2156, 922130, 5),
(8404, 'NAICS', 1513, 523, 2, 1529, 523920, 5),
(8405, 'NAICS', 931, 423, 2, 1009, 423930, 5),
(8406, 'SIC', 4311, 52, 1, 3888, 5912, 4),
(8407, 'SIC', 4313, 70, 1, 4193, 8320, 3),
(8408, 'SIC', 4305, 1, 1, 2817, 174, 4),
(8409, 'NAICS', 1813, 611, 2, 1830, 6115, 3),
(8410, 'SEC', 2360, 3230, 3, 2361, 3231, 4),
(8411, 'SEC', 2791, 20, 1, 2294, 2611, 4),
(8412, 'SIC', 4308, 20, 1, 3586, 3949, 4),
(8413, 'SIC', 4308, 20, 1, 3310, 3241, 4),
(8414, 'SIC', 3715, 5000, 2, 3757, 5091, 4),
(8415, 'SIC', 4308, 20, 1, 3311, 3250, 3),
(8416, 'SIC', 4308, 20, 1, 3189, 2679, 4),
(8417, 'NAICS', 1958, 7113, 3, 1961, 711320, 5),
(8418, 'SEC', 2791, 20, 1, 2453, 3677, 4),
(8419, 'SIC', 4308, 20, 1, 3079, 2296, 4),
(8420, 'SIC', 3419, 3500, 2, 3439, 3545, 4),
(8421, 'NAICS', 2176, 924, 2, 2178, 924110, 5),
(8422, 'SEC', 2488, 3840, 3, 2490, 3842, 4),
(8423, 'NAICS', 1943, 711, 2, 1968, 71151, 4),
(8424, 'SIC', 3548, 3790, 3, 3549, 3792, 4),
(8425, 'NAICS', 2135, 92, 1, 2174, 923140, 5),
(8426, 'NAICS', 1571, 5311, 3, 1575, 53112, 4),
(8427, 'NAICS', 1452, 517, 2, 1462, 5179, 3),
(8428, 'NAICS', 1569, 53, 1, 1580, 5312, 3),
(8429, 'SEC', 2793, 50, 1, 2582, 5065, 4),
(8430, 'SIC', 4308, 20, 1, 3270, 3061, 4),
(8431, 'NAICS', 119, 11511, 4, 125, 115116, 5),
(8432, 'NAICS', 144, 2122, 3, 148, 212221, 5),
(8433, 'NAICS', 1812, 61, 1, 1827, 61142, 4),
(8434, 'SIC', 3419, 3500, 2, 3446, 3553, 4),
(8435, 'NAICS', 1480, 52, 1, 1500, 52229, 4),
(8436, 'SIC', 4309, 40, 1, 3695, 4911, 4),
(8437, 'NAICS', 20, 11121, 4, 21, 111211, 5),
(8438, 'NAICS', 1942, 71, 1, 1954, 71121, 4),
(8439, 'NAICS', 938, 42313, 4, 937, 423130, 5),
(8440, 'SIC', 2982, 2000, 2, 3011, 2053, 4),
(8441, 'NAICS', 1836, 6116, 3, 1845, 611692, 5),
(8442, 'NAICS', 1015, 424, 2, 1074, 424820, 5),
(8443, 'SEC', 2513, 4010, 3, 2515, 4013, 4),
(8444, 'SIC', 3077, 2290, 3, 3082, 2299, 4),
(8445, 'NAICS', 1850, 62, 1, 1892, 621991, 5),
(8446, 'SEC', 2434, 3600, 2, 2456, 3690, 3),
(8447, 'SIC', 4308, 20, 1, 3272, 3080, 3),
(8448, 'SIC', 4305, 1, 1, 2829, 213, 4),
(8449, 'NAICS', 2, 111, 2, 55, 111998, 5),
(8450, 'NAICS', 1402, 51, 1, 1429, 512191, 5),
(8451, 'SIC', 2982, 2000, 2, 3035, 2092, 4),
(8452, 'SIC', 4312, 60, 1, 3959, 6310, 3),
(8453, 'SIC', 3480, 3600, 2, 3500, 3645, 4),
(8454, 'SIC', 4308, 20, 1, 3401, 3470, 3),
(8455, 'NAICS', 1625, 541, 2, 1651, 541360, 5),
(8456, 'NAICS', 1592, 5321, 3, 1595, 532112, 5),
(8457, 'NAICS', 1635, 54121, 4, 1636, 541211, 5),
(8458, 'SEC', 2731, 7380, 3, 4329, 7385, 4),
(8459, 'SIC', 3190, 2700, 2, 3195, 2730, 3),
(8460, 'NAICS', 235, 238, 2, 258, 238290, 5),
(8461, 'SIC', 2875, 900, 2, 2881, 921, 4),
(8462, 'SIC', 3886, 5900, 2, 3902, 5949, 4),
(8463, 'SIC', 3480, 3600, 2, 3516, 3676, 4),
(8464, 'NAICS', 2, 111, 2, 38, 111411, 5),
(8465, 'SIC', 3328, 3280, 3, 3329, 3281, 4),
(8466, 'NAICS', 1798, 5622, 3, 1801, 562212, 5),
(8467, 'NAICS', 1813, 611, 2, 1826, 611420, 5),
(8468, 'SEC', 2793, 50, 1, 2602, 5172, 4),
(8469, 'SEC', 2796, 70, 1, 2743, 7822, 4),
(8470, 'NAICS', 132, 21, 1, 171, 212399, 5),
(8471, 'NAICS', 1804, 5629, 3, 1806, 56291, 4),
(8472, 'SIC', 3729, 5040, 3, 3736, 5049, 4),
(8473, 'SIC', 3937, 6100, 2, 3947, 6163, 4),
(8474, 'NAICS', 1015, 424, 2, 1087, 424990, 5),
(8475, 'SIC', 3451, 3560, 3, 3458, 3567, 4),
(8476, 'SIC', 3774, 5140, 3, 3781, 5147, 4),
(8477, 'SIC', 3893, 5940, 3, 3899, 5946, 4),
(8478, 'NAICS', 930, 42, 1, 957, 42341, 4),
(8479, 'SIC', 4312, 60, 1, 3955, 6280, 3),
(8480, 'SEC', 2659, 6100, 2, 2667, 6160, 3),
(8481, 'SIC', 3180, 2670, 3, 3181, 2671, 4),
(8482, 'SEC', 2588, 5090, 3, 2590, 5099, 4),
(8483, 'SIC', 4040, 7300, 2, 4062, 7360, 3),
(8484, 'NAICS', 1776, 56171, 4, 1775, 561710, 5),
(8485, 'NAICS', 2045, 81112, 4, 2046, 811121, 5),
(8486, 'SIC', 4131, 7930, 3, 4132, 7933, 4),
(8487, 'SEC', 2283, 2500, 2, 2287, 2522, 4),
(8488, 'SIC', 4223, 8700, 2, 4236, 8741, 4),
(8489, 'SEC', 2403, 3500, 2, 2419, 3561, 4),
(8490, 'NAICS', 3, 1111, 3, 7, 11112, 4),
(8491, 'NAICS', 1402, 51, 1, 1414, 511191, 5),
(8492, 'SIC', 3395, 3460, 3, 3398, 3465, 4),
(8493, 'NAICS', 89, 1129, 3, 94, 112930, 5),
(8494, 'SEC', 2342, 3000, 2, 2344, 3011, 4),
(8495, 'SEC', 2791, 20, 1, 2456, 3690, 3),
(8496, 'SIC', 4309, 40, 1, 3649, 4490, 3),
(8497, 'NAICS', 1822, 61131, 4, 1821, 611310, 5),
(8498, 'SEC', 2512, 4000, 2, 2515, 4013, 4),
(8499, 'SIC', 3869, 5700, 2, 3872, 5713, 4),
(8500, 'NAICS', 1480, 52, 1, 1548, 524210, 5),
(8501, 'NAICS', 1813, 611, 2, 1821, 611310, 5),
(8502, 'NAICS', 138, 212, 2, 155, 212299, 5),
(8503, 'SIC', 3992, 6700, 2, 3996, 6720, 3),
(8504, 'NAICS', 1555, 5251, 3, 1557, 52511, 4),
(8505, 'SEC', 2791, 20, 1, 2257, 2090, 3),
(8506, 'SIC', 2955, 1700, 2, 2974, 1781, 4),
(8507, 'SIC', 4310, 50, 1, 3720, 5015, 4),
(8508, 'NAICS', 930, 42, 1, 1092, 42511, 4),
(8509, 'SIC', 3526, 3700, 2, 3549, 3792, 4),
(8510, 'SEC', 2791, 20, 1, 2364, 3250, 3),
(8511, 'SEC', 2403, 3500, 2, 2422, 3567, 4),
(8512, 'NAICS', 1015, 424, 2, 1023, 4242, 3),
(8513, 'NAICS', 2166, 923, 2, 2170, 923120, 5),
(8514, 'SIC', 3164, 2590, 3, 3165, 2591, 4),
(8515, 'SEC', 2403, 3500, 2, 2405, 3520, 3),
(8516, 'SEC', 2791, 20, 1, 2243, 2013, 4),
(8517, 'SIC', 3337, 3300, 2, 3345, 3321, 4),
(8518, 'SIC', 4310, 50, 1, 3801, 5194, 4),
(8519, 'NAICS', 110, 11411, 4, 112, 114112, 5),
(8520, 'SIC', 4308, 20, 1, 3495, 3639, 4),
(8521, 'SIC', 3180, 2670, 3, 3184, 2674, 4),
(8522, 'NAICS', 1859, 6213, 3, 1863, 62132, 4),
(8523, 'SIC', 4308, 20, 1, 3205, 2761, 4),
(8524, 'SIC', 3124, 2400, 2, 3132, 2431, 4),
(8525, 'SIC', 4308, 20, 1, 3380, 3430, 3),
(8526, 'NAICS', 1767, 56161, 4, 1768, 561611, 5),
(8527, 'SIC', 3715, 5000, 2, 3734, 5047, 4),
(8528, 'SIC', 3869, 5700, 2, 3870, 5710, 3),
(8529, 'NAICS', 205, 23, 1, 244, 23814, 4),
(8530, 'SIC', 4308, 20, 1, 3001, 2041, 4),
(8531, 'SIC', 4308, 20, 1, 3095, 2335, 4),
(8532, 'SIC', 4139, 7990, 3, 4140, 7991, 4),
(8533, 'NAICS', 1725, 56, 1, 1794, 56211, 4),
(8534, 'NAICS', 2037, 81, 1, 2124, 81392, 4),
(8535, 'SIC', 4313, 70, 1, 4092, 7534, 4),
(8536, 'SIC', 3797, 5190, 3, 3798, 5191, 4),
(8537, 'NAICS', 931, 423, 2, 984, 42371, 4),
(8538, 'NAICS', 1725, 56, 1, 1770, 561613, 5),
(8539, 'SIC', 4114, 7810, 3, 4116, 7819, 4),
(8540, 'NAICS', 205, 23, 1, 243, 238140, 5),
(8541, 'SEC', 2517, 4200, 2, 2521, 4230, 3),
(8542, 'SIC', 3606, 4110, 3, 3607, 4111, 4),
(8543, 'SIC', 2931, 1470, 3, 2932, 1474, 4),
(8544, 'NAICS', 1403, 511, 2, 1411, 511140, 5),
(8545, 'NAICS', 1942, 71, 1, 1980, 7131, 3),
(8546, 'SIC', 4313, 70, 1, 4179, 8210, 3),
(8547, 'NAICS', 1035, 4244, 3, 1042, 424440, 5),
(8548, 'SIC', 4305, 1, 1, 2849, 711, 4),
(8549, 'SEC', 2479, 3820, 3, 2481, 3822, 4),
(8550, 'SEC', 2434, 3600, 2, 2453, 3677, 4),
(8551, 'SIC', 4306, 10, 1, 2924, 1429, 4),
(8552, 'SIC', 4309, 40, 1, 3651, 4492, 4),
(8553, 'NAICS', 1562, 5259, 3, 1563, 525910, 5),
(8554, 'SIC', 4007, 7000, 2, 4010, 7020, 3),
(8555, 'NAICS', 2023, 72231, 4, 2022, 722310, 5),
(8556, 'NAICS', 934, 42311, 4, 933, 423110, 5),
(8557, 'NAICS', 1650, 54135, 4, 1649, 541350, 5),
(8558, 'NAICS', 1725, 56, 1, 1774, 5617, 3),
(8559, 'NAICS', 1859, 6213, 3, 1864, 621330, 5),
(8560, 'NAICS', 2205, 9281, 3, 2209, 92812, 4),
(8561, 'NAICS', 2017, 7213, 3, 2019, 72131, 4),
(8562, 'NAICS', 1812, 61, 1, 1849, 61171, 4),
(8563, 'SIC', 4192, 8300, 2, 4195, 8330, 3),
(8564, 'NAICS', 1506, 5223, 3, 1508, 52231, 4),
(8565, 'NAICS', 1624, 54, 1, 1658, 541410, 5),
(8566, 'SIC', 2847, 700, 2, 2862, 761, 4),
(8567, 'SIC', 4308, 20, 1, 3312, 3251, 4),
(8568, 'SIC', 2884, 1000, 2, 2897, 1081, 4),
(8569, 'SIC', 2884, 1000, 2, 2891, 1040, 3),
(8570, 'SIC', 3835, 5490, 3, 3836, 5499, 4),
(8571, 'SIC', 4314, 90, 1, 4277, 9500, 2),
(8572, 'NAICS', 1536, 524, 2, 1549, 52421, 4),
(8573, 'SEC', 2568, 5000, 2, 2576, 5047, 4),
(8574, 'SIC', 4308, 20, 1, 3318, 3262, 4),
(8575, 'SEC', 2796, 70, 1, 2750, 7948, 4),
(8576, 'NAICS', 43, 1119, 3, 50, 111940, 5),
(8577, 'SIC', 3974, 6400, 2, 3976, 6411, 4),
(8578, 'NAICS', 1624, 54, 1, 1639, 541219, 5),
(8579, 'SIC', 4306, 10, 1, 2908, 1241, 4),
(8580, 'SEC', 2552, 4900, 2, 2564, 4950, 3),
(8581, 'SEC', 2796, 70, 1, 2733, 7384, 4),
(8582, 'NAICS', 946, 4233, 3, 952, 42333, 4),
(8583, 'SEC', 2792, 40, 1, 4316, 4955, 3),
(8584, 'SEC', 2793, 50, 1, 2586, 5082, 4),
(8585, 'SIC', 4308, 20, 1, 3356, 3351, 4),
(8586, 'SIC', 3344, 3320, 3, 3346, 3322, 4),
(8587, 'SIC', 4309, 40, 1, 3621, 4210, 3),
(8588, 'SIC', 3190, 2700, 2, 3205, 2761, 4),
(8589, 'SEC', 2372, 3310, 3, 2373, 3312, 4),
(8590, 'NAICS', 1076, 4249, 3, 1083, 424940, 5),
(8591, 'NAICS', 1942, 71, 1, 1993, 713920, 5),
(8592, 'SIC', 2798, 100, 2, 2816, 173, 4),
(8593, 'SIC', 2834, 250, 3, 2839, 259, 4),
(8594, 'SIC', 4312, 60, 1, 3997, 6722, 4),
(8595, 'NAICS', 1485, 522, 2, 1503, 522293, 5),
(8596, 'NAICS', 1443, 5151, 3, 1448, 51512, 4),
(8597, 'SIC', 3480, 3600, 2, 3524, 3695, 4),
(8598, 'SEC', 2458, 3700, 2, 2469, 3730, 3),
(8599, 'SIC', 3977, 6500, 2, 3983, 6517, 4),
(8600, 'SEC', 2795, 60, 1, 2707, 6798, 4),
(8601, 'SIC', 4308, 20, 1, 3230, 2840, 3),
(8602, 'NAICS', 180, 22, 1, 184, 221111, 5),
(8603, 'SIC', 4040, 7300, 2, 4042, 7311, 4),
(8604, 'SIC', 3148, 2500, 2, 3153, 2515, 4),
(8605, 'SIC', 3337, 3300, 2, 3352, 3339, 4),
(8606, 'SIC', 4313, 70, 1, 4093, 7536, 4),
(8607, 'NAICS', 1015, 424, 2, 1048, 424470, 5),
(8608, 'SEC', 2791, 20, 1, 2470, 3740, 3),
(8609, 'NAICS', 1061, 4246, 3, 1064, 424690, 5),
(8610, 'NAICS', 1850, 62, 1, 1898, 6222, 3),
(8611, 'SEC', 2517, 4200, 2, 2522, 4231, 4),
(8612, 'NAICS', 1871, 6214, 3, 1880, 621498, 5),
(8613, 'SIC', 4308, 20, 1, 3145, 2491, 4),
(8614, 'NAICS', 198, 2213, 3, 204, 22133, 4),
(8615, 'NAICS', 1419, 512, 2, 1433, 51221, 4),
(8616, 'SIC', 4308, 20, 1, 3290, 3144, 4),
(8617, 'SIC', 3680, 4800, 2, 3685, 4822, 4),
(8618, 'NAICS', 1, 11, 1, 120, 115111, 5),
(8619, 'NAICS', 1953, 7112, 3, 1954, 71121, 4),
(8620, 'NAICS', 2004, 721, 2, 2018, 721310, 5),
(8621, 'SIC', 3148, 2500, 2, 3156, 2520, 3),
(8622, 'NAICS', 1598, 5322, 3, 1601, 532220, 5),
(8623, 'SIC', 3371, 3400, 2, 3413, 3494, 4),
(8624, 'NAICS', 1850, 62, 1, 1936, 6243, 3),
(8625, 'NAICS', 2136, 921, 2, 2137, 9211, 3),
(8626, 'SIC', 3330, 3290, 3, 3333, 3295, 4),
(8627, 'NAICS', 1942, 71, 1, 1998, 71394, 4),
(8628, 'SIC', 3649, 4490, 3, 3653, 4499, 4),
(8629, 'SIC', 4311, 52, 1, 3874, 5719, 4),
(8630, 'NAICS', 1412, 51114, 4, 1411, 511140, 5),
(8631, 'SIC', 4247, 9100, 2, 4255, 9191, 4),
(8632, 'NAICS', 27, 11132, 4, 26, 111320, 5),
(8633, 'NAICS', 1458, 51721, 4, 1457, 517210, 5),
(8634, 'NAICS', 1813, 611, 2, 1833, 611512, 5),
(8635, 'NAICS', 1703, 54187, 4, 1702, 541870, 5),
(8636, 'SIC', 3715, 5000, 2, 3753, 5085, 4),
(8637, 'SIC', 4313, 70, 1, 4073, 7378, 4),
(8638, 'NAICS', 1729, 56111, 4, 1728, 561110, 5),
(8639, 'SEC', 2641, 5910, 3, 2642, 5912, 4),
(8640, 'SIC', 3083, 2300, 2, 3093, 2330, 3),
(8641, 'SIC', 4305, 1, 1, 2874, 851, 4),
(8642, 'SIC', 4314, 90, 1, 4249, 9111, 4),
(8643, 'NAICS', 1634, 5412, 3, 1636, 541211, 5),
(8644, 'NAICS', 1591, 532, 2, 1596, 532120, 5),
(8645, 'SEC', 2302, 2700, 2, 2311, 2741, 4),
(8646, 'SEC', 2673, 6220, 3, 2674, 6221, 4),
(8647, 'NAICS', 931, 423, 2, 938, 42313, 4),
(8648, 'SEC', 2789, 10, 1, 2219, 1220, 3),
(8649, 'NAICS', 975, 4236, 3, 976, 423610, 5),
(8650, 'NAICS', 1624, 54, 1, 1656, 54138, 4),
(8651, 'SIC', 4125, 7900, 2, 4143, 7996, 4),
(8652, 'NAICS', 1402, 51, 1, 1439, 51224, 4),
(8653, 'SIC', 3137, 2440, 3, 3140, 2449, 4),
(8654, 'NAICS', 1591, 532, 2, 1609, 5323, 3),
(8655, 'SIC', 2909, 1300, 2, 2914, 1380, 3),
(8656, 'NAICS', 57, 1121, 3, 58, 11211, 4),
(8657, 'NAICS', 1774, 5617, 3, 1778, 56172, 4),
(8658, 'SIC', 3815, 5300, 2, 3818, 5330, 3),
(8659, 'SIC', 4313, 70, 1, 4046, 7320, 3),
(8660, 'NAICS', 1782, 56174, 4, 1781, 561740, 5),
(8661, 'SIC', 4306, 10, 1, 2903, 1221, 4),
(8662, 'NAICS', 183, 22111, 4, 189, 221116, 5),
(8663, 'SEC', 2562, 4940, 3, 2563, 4941, 4),
(8664, 'SIC', 4037, 7290, 3, 4039, 7299, 4),
(8665, 'SIC', 4113, 7800, 2, 4116, 7819, 4),
(8666, 'SIC', 3282, 3100, 2, 3288, 3142, 4),
(8667, 'NAICS', 1813, 611, 2, 1846, 611699, 5),
(8668, 'SIC', 2939, 1500, 2, 2944, 1531, 4),
(8669, 'NAICS', 1, 11, 1, 116, 11421, 4),
(8670, 'NAICS', 2137, 9211, 3, 2149, 92119, 4),
(8671, 'SIC', 3124, 2400, 2, 3131, 2430, 3),
(8672, 'SEC', 2792, 40, 1, 2566, 4960, 3),
(8673, 'NAICS', 1921, 6241, 3, 1922, 624110, 5),
(8674, 'NAICS', 2003, 72, 1, 2022, 722310, 5),
(8675, 'SIC', 4308, 20, 1, 3455, 3564, 4),
(8676, 'SIC', 3576, 3900, 2, 3587, 3950, 3),
(8677, 'SEC', 2323, 2830, 3, 2327, 2836, 4),
(8678, 'SIC', 3716, 5010, 3, 3720, 5015, 4),
(8679, 'NAICS', 1725, 56, 1, 1810, 562991, 5),
(8680, 'SIC', 3526, 3700, 2, 3529, 3713, 4),
(8681, 'SIC', 4308, 20, 1, 3385, 3441, 4),
(8682, 'SIC', 3167, 2600, 2, 3174, 2650, 3),
(8683, 'SIC', 4310, 50, 1, 3744, 5070, 3),
(8684, 'NAICS', 1, 11, 1, 81, 11241, 4),
(8685, 'NAICS', 235, 238, 2, 275, 23891, 4),
(8686, 'NAICS', 1486, 5221, 3, 1490, 52212, 4),
(8687, 'SIC', 4107, 7640, 3, 4108, 7641, 4),
(8688, 'SEC', 2418, 3560, 3, 2421, 3564, 4),
(8689, 'SEC', 2568, 5000, 2, 2585, 5080, 3),
(8690, 'SIC', 3577, 3910, 3, 3580, 3915, 4),
(8691, 'NAICS', 1942, 71, 1, 1992, 71391, 4),
(8692, 'NAICS', 1470, 519, 2, 1477, 51913, 4),
(8693, 'SIC', 2931, 1470, 3, 2933, 1475, 4),
(8694, 'SIC', 3434, 3540, 3, 3443, 3549, 4),
(8695, 'SIC', 3715, 5000, 2, 3725, 5031, 4),
(8696, 'NAICS', 1725, 56, 1, 1727, 5611, 3),
(8697, 'SIC', 3474, 3590, 3, 3478, 3596, 4),
(8698, 'NAICS', 1015, 424, 2, 1032, 42433, 4),
(8699, 'SIC', 2894, 1060, 3, 2895, 1061, 4),
(8700, 'SIC', 4308, 20, 1, 3073, 2280, 3),
(8701, 'NAICS', 930, 42, 1, 1030, 42432, 4),
(8702, 'NAICS', 1640, 5413, 3, 1651, 541360, 5),
(8703, 'SIC', 3937, 6100, 2, 3946, 6162, 4),
(8704, 'NAICS', 1419, 512, 2, 1435, 51222, 4),
(8705, 'SIC', 3444, 3550, 3, 3449, 3556, 4),
(8706, 'SIC', 3337, 3300, 2, 3370, 3399, 4),
(8707, 'SIC', 4308, 20, 1, 3592, 3960, 3),
(8708, 'SIC', 4312, 60, 1, 3962, 6321, 4),
(8709, 'SEC', 2240, 2000, 2, 2244, 2015, 4),
(8710, 'SIC', 4310, 50, 1, 3769, 5130, 3),
(8711, 'NAICS', 930, 42, 1, 963, 42344, 4),
(8712, 'NAICS', 2150, 922, 2, 2164, 922190, 5),
(8713, 'SEC', 2796, 70, 1, 2720, 7350, 3),
(8714, 'NAICS', 2071, 812, 2, 2081, 812210, 5),
(8715, 'SIC', 3854, 5600, 2, 3861, 5640, 3),
(8716, 'SIC', 4081, 7500, 2, 4099, 7549, 4),
(8717, 'NAICS', 1452, 517, 2, 1456, 5172, 3),
(8718, 'SIC', 3372, 3410, 3, 3373, 3411, 4),
(8719, 'SIC', 4305, 1, 1, 2835, 251, 4),
(8720, 'NAICS', 1726, 561, 2, 1782, 56174, 4),
(8721, 'SIC', 4308, 20, 1, 3052, 2211, 4),
(8722, 'SIC', 4306, 10, 1, 2918, 1400, 2),
(8723, 'NAICS', 2003, 72, 1, 2028, 7224, 3),
(8724, 'NAICS', 1402, 51, 1, 1444, 51511, 4),
(8725, 'NAICS', 1598, 5322, 3, 1602, 53222, 4),
(8726, 'SIC', 3762, 5100, 2, 3772, 5137, 4),
(8727, 'NAICS', 1672, 5416, 3, 1682, 54169, 4),
(8728, 'NAICS', 2038, 811, 2, 2060, 81131, 4),
(8729, 'NAICS', 2032, 72251, 4, 2033, 722511, 5),
(8730, 'SIC', 3301, 3200, 2, 3313, 3253, 4),
(8731, 'NAICS', 930, 42, 1, 1072, 424810, 5),
(8732, 'NAICS', 1, 11, 1, 67, 11221, 4),
(8733, 'SEC', 2283, 2500, 2, 2291, 2590, 3),
(8734, 'NAICS', 2071, 812, 2, 2085, 8123, 3),
(8735, 'NAICS', 2135, 92, 1, 2204, 928, 2),
(8736, 'SIC', 3316, 3260, 3, 3321, 3269, 4),
(8737, 'NAICS', 1485, 522, 2, 1496, 522210, 5),
(8738, 'NAICS', 1850, 62, 1, 1861, 62131, 4),
(8739, 'NAICS', 1774, 5617, 3, 1783, 561790, 5),
(8740, 'SIC', 2905, 1230, 3, 2906, 1231, 4),
(8741, 'SIC', 4308, 20, 1, 3108, 2380, 3),
(8742, 'NAICS', 1979, 713, 2, 2000, 71395, 4),
(8743, 'SIC', 3693, 4900, 2, 3699, 4924, 4),
(8744, 'SEC', 2791, 20, 1, 2351, 3086, 4),
(8745, 'SIC', 3301, 3200, 2, 3305, 3221, 4),
(8746, 'NAICS', 1851, 621, 2, 1888, 6219, 3),
(8747, 'SEC', 2791, 20, 1, 2274, 2340, 3),
(8748, 'SEC', 2552, 4900, 2, 2556, 4922, 4),
(8749, 'NAICS', 2039, 8111, 3, 2044, 811118, 5),
(8750, 'SIC', 4313, 70, 1, 4177, 8111, 4),
(8751, 'SIC', 3371, 3400, 2, 3408, 3489, 4),
(8752, 'NAICS', 1851, 621, 2, 1880, 621498, 5),
(8753, 'SEC', 2791, 20, 1, 2506, 3942, 4),
(8754, 'SIC', 3837, 5500, 2, 3853, 5599, 4),
(8755, 'NAICS', 2151, 9221, 3, 2161, 92215, 4),
(8756, 'NAICS', 1942, 71, 1, 1949, 711130, 5),
(8757, 'SIC', 4100, 7600, 2, 4106, 7631, 4),
(8758, 'SIC', 3050, 2200, 2, 3067, 2260, 3),
(8759, 'NAICS', 2135, 92, 1, 2159, 92214, 4),
(8760, 'SEC', 2500, 3900, 2, 2510, 3960, 3),
(8761, 'SIC', 4311, 52, 1, 3861, 5640, 3),
(8762, 'SIC', 4308, 20, 1, 3558, 3823, 4),
(8763, 'SIC', 4307, 15, 1, 2962, 1740, 3),
(8764, 'NAICS', 1605, 53229, 4, 1608, 532299, 5),
(8765, 'SEC', 2229, 1500, 2, 2233, 1540, 3),
(8766, 'SIC', 3220, 2820, 3, 3223, 2823, 4),
(8767, 'SIC', 4308, 20, 1, 3223, 2823, 4),
(8768, 'SIC', 4113, 7800, 2, 4124, 7841, 4),
(8769, 'NAICS', 1771, 56162, 4, 1772, 561621, 5),
(8770, 'NAICS', 1754, 56149, 4, 1755, 561491, 5),
(8771, 'SIC', 4313, 70, 1, 4240, 8748, 4),
(8772, 'NAICS', 1979, 713, 2, 1990, 7139, 3),
(8773, 'NAICS', 1943, 711, 2, 1952, 71119, 4),
(8774, 'NAICS', 108, 114, 2, 110, 11411, 4),
(8775, 'NAICS', 1904, 623, 2, 1910, 62321, 4),
(8776, 'SEC', 2276, 2400, 2, 2281, 2451, 4),
(8777, 'SIC', 4311, 52, 1, 3826, 5421, 4),
(8778, 'NAICS', 1480, 52, 1, 1485, 522, 2),
(8779, 'SIC', 3337, 3300, 2, 3367, 3369, 4),
(8780, 'SEC', 2713, 7300, 2, 2714, 7310, 3),
(8781, 'SIC', 3050, 2200, 2, 3062, 2253, 4),
(8782, 'NAICS', 1840, 61162, 4, 1839, 611620, 5),
(8783, 'SEC', 2319, 2800, 2, 2336, 2891, 4),
(8784, 'SEC', 2677, 6300, 2, 2683, 6330, 3),
(8785, 'SIC', 3707, 4950, 3, 3708, 4952, 4),
(8786, 'NAICS', 1452, 517, 2, 1455, 51711, 4),
(8787, 'NAICS', 1726, 561, 2, 1758, 5615, 3),
(8788, 'NAICS', 2, 111, 2, 16, 11119, 4),
(8789, 'NAICS', 1898, 6222, 3, 1900, 62221, 4),
(8790, 'NAICS', 1847, 6117, 3, 1848, 611710, 5),
(8791, 'SEC', 2403, 3500, 2, 2407, 3524, 4),
(8792, 'SIC', 4308, 20, 1, 3302, 3210, 3),
(8793, 'SEC', 2649, 6000, 2, 2656, 6036, 4),
(8794, 'SEC', 2791, 20, 1, 2480, 3821, 4),
(8795, 'SIC', 2982, 2000, 2, 2989, 2022, 4),
(8796, 'NAICS', 1920, 624, 2, 1935, 62423, 4),
(8797, 'SEC', 2713, 7300, 2, 2731, 7380, 3),
(8798, 'NAICS', 1513, 523, 2, 1517, 523120, 5),
(8799, 'SIC', 2939, 1500, 2, 2945, 1540, 3),
(8800, 'SEC', 2660, 6110, 3, 2661, 6111, 4),
(8801, 'SIC', 3804, 5200, 2, 3808, 5231, 4),
(8802, 'NAICS', 1725, 56, 1, 1748, 561431, 5),
(8803, 'NAICS', 117, 115, 2, 128, 11521, 4),
(8804, 'SIC', 3214, 2800, 2, 3218, 2816, 4),
(8805, 'SIC', 3190, 2700, 2, 3199, 2741, 4),
(8806, 'NAICS', 89, 1129, 3, 96, 112990, 5),
(8807, 'SIC', 3167, 2600, 2, 3188, 2678, 4),
(8808, 'SIC', 4306, 10, 1, 2925, 1440, 3),
(8809, 'SIC', 3124, 2400, 2, 3129, 2426, 4),
(8810, 'SIC', 3409, 3490, 3, 3411, 3492, 4),
(8811, 'SIC', 3301, 3200, 2, 3306, 3229, 4),
(8812, 'SIC', 4308, 20, 1, 3100, 2342, 4),
(8813, 'NAICS', 234, 23799, 4, 233, 237990, 5),
(8814, 'NAICS', 218, 237, 2, 230, 237310, 5),
(8815, 'SIC', 4308, 20, 1, 3537, 3730, 3),
(8816, 'NAICS', 1, 11, 1, 129, 1153, 3),
(8817, 'NAICS', 1015, 424, 2, 1038, 424420, 5),
(8818, 'NAICS', 45, 11191, 4, 44, 111910, 5),
(8819, 'SEC', 2539, 4800, 2, 2551, 4899, 4),
(8820, 'NAICS', 1442, 515, 2, 1450, 515210, 5),
(8821, 'NAICS', 1, 11, 1, 75, 112340, 5),
(8822, 'SIC', 2982, 2000, 2, 2988, 2021, 4),
(8823, 'SIC', 4309, 40, 1, 3638, 4412, 4),
(8824, 'SIC', 3893, 5940, 3, 3898, 5945, 4),
(8825, 'NAICS', 1966, 7115, 3, 1968, 71151, 4),
(8826, 'SIC', 3301, 3200, 2, 3332, 3292, 4),
(8827, 'SEC', 2791, 20, 1, 2438, 3620, 3),
(8828, 'NAICS', 2003, 72, 1, 2020, 722, 2),
(8829, 'SIC', 4308, 20, 1, 3049, 2141, 4),
(8830, 'SEC', 2292, 2600, 2, 2298, 2631, 4),
(8831, 'SIC', 4308, 20, 1, 3013, 2061, 4),
(8832, 'SIC', 4308, 20, 1, 3216, 2812, 4),
(8833, 'SIC', 4308, 20, 1, 3213, 2796, 4),
(8834, 'SEC', 2650, 6020, 3, 2653, 6029, 4),
(8835, 'SIC', 4308, 20, 1, 3278, 3086, 4),
(8836, 'SIC', 4308, 20, 1, 3006, 2047, 4),
(8837, 'SEC', 2746, 7840, 3, 2747, 7841, 4),
(8838, 'NAICS', 2182, 925, 2, 2185, 92511, 4),
(8839, 'SIC', 4308, 20, 1, 3467, 3579, 4),
(8840, 'SIC', 3686, 4830, 3, 3687, 4832, 4),
(8841, 'NAICS', 1942, 71, 1, 1973, 712120, 5),
(8842, 'SIC', 4313, 70, 1, 4187, 8243, 4),
(8843, 'NAICS', 930, 42, 1, 981, 42369, 4),
(8844, 'SIC', 4058, 7350, 3, 4061, 7359, 4),
(8845, 'SIC', 4313, 70, 1, 4151, 8030, 3),
(8846, 'SEC', 2539, 4800, 2, 2543, 4820, 3),
(8847, 'SIC', 4313, 70, 1, 4039, 7299, 4),
(8848, 'SIC', 4305, 1, 1, 2837, 253, 4),
(8849, 'SIC', 4313, 70, 1, 4050, 7331, 4),
(8850, 'SEC', 4322, 6180, 3, 4323, 6189, 4),
(8851, 'SEC', 2713, 7300, 2, 2724, 7363, 4),
(8852, 'SEC', 2446, 3660, 3, 2447, 3661, 4),
(8853, 'SIC', 4306, 10, 1, 2936, 1481, 4),
(8854, 'NAICS', 1958, 7113, 3, 1962, 71132, 4),
(8855, 'NAICS', 2117, 8134, 3, 2118, 813410, 5),
(8856, 'SIC', 4178, 8200, 2, 4188, 8244, 4),
(8857, 'SIC', 4311, 52, 1, 3901, 5948, 4),
(8858, 'NAICS', 2071, 812, 2, 2073, 81211, 4),
(8859, 'SIC', 4178, 8200, 2, 4190, 8290, 3),
(8860, 'SEC', 2796, 70, 1, 2749, 7940, 3),
(8861, 'NAICS', 235, 238, 2, 259, 23829, 4),
(8862, 'SIC', 3620, 4200, 2, 3628, 4222, 4),
(8863, 'SIC', 4312, 60, 1, 3981, 6514, 4),
(8864, 'SIC', 4313, 70, 1, 4216, 8641, 4),
(8865, 'SIC', 4313, 70, 1, 4077, 7382, 4),
(8866, 'SEC', 2791, 20, 1, 2339, 2911, 4),
(8867, 'SEC', 2796, 70, 1, 2727, 7372, 4),
(8868, 'NAICS', 1486, 5221, 3, 1491, 522130, 5),
(8869, 'SEC', 2659, 6100, 2, 4325, 6199, 4),
(8870, 'SIC', 4313, 70, 1, 4134, 7941, 4),
(8871, 'SIC', 3886, 5900, 2, 3912, 5992, 4),
(8872, 'SIC', 2826, 210, 3, 2828, 212, 4),
(8873, 'NAICS', 1624, 54, 1, 1686, 541712, 5),
(8874, 'NAICS', 1554, 525, 2, 1560, 525190, 5),
(8875, 'NAICS', 1726, 561, 2, 1749, 561439, 5),
(8876, 'SEC', 2517, 4200, 2, 2520, 4220, 3),
(8877, 'SIC', 4308, 20, 1, 3074, 2281, 4),
(8878, 'NAICS', 139, 2121, 3, 143, 212113, 5),
(8879, 'NAICS', 2, 111, 2, 3, 1111, 3),
(8880, 'SEC', 2240, 2000, 2, 2243, 2013, 4),
(8881, 'NAICS', 174, 21311, 4, 175, 213111, 5),
(8882, 'SEC', 2710, 7010, 3, 2711, 7011, 4),
(8883, 'NAICS', 3, 1111, 3, 11, 11114, 4),
(8884, 'NAICS', 1624, 54, 1, 1650, 54135, 4),
(8885, 'SIC', 4308, 20, 1, 3540, 3740, 3),
(8886, 'NAICS', 982, 4237, 3, 987, 423730, 5),
(8887, 'NAICS', 132, 21, 1, 140, 21211, 4),
(8888, 'NAICS', 1624, 54, 1, 1655, 541380, 5),
(8889, 'SEC', 2319, 2800, 2, 2325, 2834, 4),
(8890, 'SIC', 4308, 20, 1, 3150, 2511, 4),
(8891, 'SIC', 2847, 700, 2, 2866, 782, 4),
(8892, 'NAICS', 89, 1129, 3, 93, 11292, 4),
(8893, 'SEC', 2610, 5300, 2, 2613, 5330, 3),
(8894, 'NAICS', 1591, 532, 2, 1598, 5322, 3),
(8895, 'NAICS', 1035, 4244, 3, 1044, 424450, 5),
(8896, 'SEC', 2240, 2000, 2, 2257, 2090, 3),
(8897, 'SIC', 4295, 9660, 3, 4296, 9661, 4),
(8898, 'SEC', 2794, 52, 1, 2611, 5310, 3),
(8899, 'SIC', 2864, 780, 3, 2866, 782, 4),
(8900, 'NAICS', 1480, 52, 1, 1492, 52213, 4),
(8901, 'SEC', 2795, 60, 1, 2691, 6400, 2),
(8902, 'NAICS', 180, 22, 1, 183, 22111, 4),
(8903, 'NAICS', 1741, 5614, 3, 1743, 56141, 4),
(8904, 'NAICS', 1646, 54133, 4, 1645, 541330, 5),
(8905, 'SIC', 3214, 2800, 2, 3232, 2842, 4),
(8906, 'NAICS', 1030, 42432, 4, 1029, 424320, 5),
(8907, 'SIC', 3371, 3400, 2, 3381, 3431, 4),
(8908, 'NAICS', 144, 2122, 3, 149, 212222, 5),
(8909, 'SIC', 3252, 2900, 2, 3257, 2952, 4),
(8910, 'SEC', 2738, 7800, 2, 2746, 7840, 3),
(8911, 'NAICS', 2182, 925, 2, 2184, 925110, 5),
(8912, 'NAICS', 1054, 4245, 3, 1058, 42452, 4),
(8913, 'NAICS', 1023, 4242, 3, 1025, 42421, 4),
(8914, 'NAICS', 1066, 4247, 3, 1070, 42472, 4),
(8915, 'NAICS', 1485, 522, 2, 1486, 5221, 3),
(8916, 'NAICS', 218, 237, 2, 226, 2372, 3),
(8917, 'SIC', 3869, 5700, 2, 3871, 5712, 4),
(8918, 'SIC', 3148, 2500, 2, 3164, 2590, 3),
(8919, 'NAICS', 1624, 54, 1, 1700, 541860, 5),
(8920, 'NAICS', 2113, 81331, 4, 2114, 813311, 5),
(8921, 'SIC', 4007, 7000, 2, 4012, 7030, 3),
(8922, 'NAICS', 1054, 4245, 3, 1057, 424520, 5),
(8923, 'SIC', 3527, 3710, 3, 3529, 3713, 4),
(8924, 'SEC', 2791, 20, 1, 2288, 2530, 3),
(8925, 'SIC', 3404, 3480, 3, 3407, 3484, 4),
(8926, 'SEC', 2791, 20, 1, 2373, 3312, 4),
(8927, 'NAICS', 995, 42382, 4, 994, 423820, 5),
(8928, 'SIC', 3948, 6200, 2, 3952, 6221, 4),
(8929, 'NAICS', 2103, 813, 2, 2128, 81394, 4),
(8930, 'SIC', 4310, 50, 1, 3797, 5190, 3),
(8931, 'NAICS', 1404, 5111, 3, 1415, 511199, 5),
(8932, 'SIC', 3552, 3800, 2, 3569, 3845, 4),
(8933, 'SEC', 2791, 20, 1, 2323, 2830, 3),
(8934, 'NAICS', 1989, 71329, 4, 1988, 713290, 5),
(8935, 'SEC', 2774, 8700, 2, 2783, 8744, 4),
(8936, 'SIC', 4250, 9120, 3, 4251, 9121, 4),
(8937, 'NAICS', 1792, 562, 2, 1811, 562998, 5),
(8938, 'NAICS', 1943, 711, 2, 1966, 7115, 3),
(8939, 'SIC', 2982, 2000, 2, 2983, 2010, 3),
(8940, 'SIC', 4175, 8100, 2, 4176, 8110, 3),
(8941, 'SIC', 4311, 52, 1, 3914, 5994, 4),
(8942, 'NAICS', 1624, 54, 1, 1637, 541213, 5),
(8943, 'SIC', 2825, 200, 2, 2827, 211, 4),
(8944, 'SIC', 3762, 5100, 2, 3791, 5170, 3),
(8945, 'SIC', 4081, 7500, 2, 4088, 7521, 4),
(8946, 'SIC', 4309, 40, 1, 3640, 4424, 4),
(8947, 'SIC', 4308, 20, 1, 3336, 3299, 4),
(8948, 'NAICS', 1471, 5191, 3, 1479, 51919, 4),
(8949, 'NAICS', 1500, 52229, 4, 1503, 522293, 5),
(8950, 'SIC', 4308, 20, 1, 3438, 3544, 4),
(8951, 'SEC', 2526, 4500, 2, 2531, 4522, 4),
(8952, 'SEC', 2384, 3400, 2, 2400, 3470, 3),
(8953, 'NAICS', 147, 21222, 4, 149, 212222, 5),
(8954, 'SEC', 2770, 8300, 2, 2771, 8350, 3),
(8955, 'SIC', 3667, 4700, 2, 3678, 4785, 4),
(8956, 'NAICS', 1554, 525, 2, 1565, 525920, 5),
(8957, 'SEC', 2791, 20, 1, 2360, 3230, 3),
(8958, 'SIC', 4308, 20, 1, 3287, 3140, 3),
(8959, 'SEC', 2791, 20, 1, 2363, 3241, 4),
(8960, 'SEC', 2671, 6210, 3, 2672, 6211, 4),
(8961, 'NAICS', 1850, 62, 1, 1851, 621, 2),
(8962, 'SEC', 2793, 50, 1, 2604, 5190, 3),
(8963, 'NAICS', 181, 221, 2, 191, 221118, 5),
(8964, 'NAICS', 206, 236, 2, 214, 236210, 5),
(8965, 'SIC', 3715, 5000, 2, 3738, 5051, 4),
(8966, 'SIC', 3167, 2600, 2, 3168, 2610, 3),
(8967, 'NAICS', 172, 213, 2, 179, 213115, 5),
(8968, 'NAICS', 1725, 56, 1, 1735, 561311, 5),
(8969, 'SEC', 2791, 20, 1, 2270, 2273, 4),
(8970, 'SIC', 4017, 7200, 2, 4019, 7211, 4),
(8971, 'SIC', 3480, 3600, 2, 3493, 3634, 4),
(8972, 'SIC', 3886, 5900, 2, 3910, 5989, 4),
(8973, 'SEC', 2795, 60, 1, 2661, 6111, 4),
(8974, 'SIC', 3837, 5500, 2, 3840, 5520, 3),
(8975, 'NAICS', 1, 11, 1, 95, 11293, 4),
(8976, 'NAICS', 1943, 711, 2, 1963, 7114, 3),
(8977, 'SIC', 4308, 20, 1, 3111, 2385, 4),
(8978, 'NAICS', 1480, 52, 1, 1564, 52591, 4),
(8979, 'NAICS', 2205, 9281, 3, 2208, 928120, 5),
(8980, 'SEC', 2654, 6030, 3, 2656, 6036, 4),
(8981, 'NAICS', 1591, 532, 2, 1592, 5321, 3),
(8982, 'SIC', 3852, 5590, 3, 3853, 5599, 4),
(8983, 'NAICS', 1744, 56142, 4, 1746, 561422, 5),
(8984, 'SIC', 3877, 5730, 3, 3879, 5734, 4),
(8985, 'SIC', 3886, 5900, 2, 3900, 5947, 4),
(8986, 'NAICS', 1470, 519, 2, 1478, 519190, 5),
(8987, 'SIC', 3420, 3510, 3, 3422, 3519, 4),
(8988, 'SEC', 2796, 70, 1, 2742, 7820, 3),
(8989, 'SEC', 2434, 3600, 2, 2438, 3620, 3),
(8990, 'SIC', 4312, 60, 1, 3922, 6021, 4),
(8991, 'NAICS', 235, 238, 2, 247, 238160, 5),
(8992, 'SIC', 4312, 60, 1, 3991, 6553, 4),
(8993, 'NAICS', 1, 11, 1, 6, 111120, 5),
(8994, 'SEC', 2384, 3400, 2, 2393, 3443, 4),
(8995, 'SIC', 3992, 6700, 2, 4004, 6794, 4),
(8996, 'SEC', 2795, 60, 1, 2676, 6282, 4),
(8997, 'NAICS', 68, 1123, 3, 72, 11232, 4),
(8998, 'NAICS', 1758, 5615, 3, 1764, 561591, 5),
(8999, 'NAICS', 1597, 53212, 4, 1596, 532120, 5),
(9000, 'SIC', 2975, 1790, 3, 2977, 1793, 4),
(9001, 'NAICS', 1823, 6114, 3, 1828, 611430, 5),
(9002, 'NAICS', 1, 11, 1, 41, 111421, 5),
(9003, 'SEC', 2591, 5100, 2, 2600, 5170, 3),
(9004, 'SIC', 4100, 7600, 2, 4110, 7692, 4),
(9005, 'NAICS', 2137, 9211, 3, 2145, 92114, 4),
(9006, 'SIC', 3937, 6100, 2, 3944, 6159, 4),
(9007, 'NAICS', 2071, 812, 2, 2088, 812320, 5),
(9008, 'SIC', 4146, 8000, 2, 4163, 8062, 4),
(9009, 'SEC', 2795, 60, 1, 2662, 6140, 3),
(9010, 'SEC', 2434, 3600, 2, 2452, 3674, 4),
(9011, 'SIC', 3301, 3200, 2, 3327, 3275, 4),
(9012, 'SIC', 4313, 70, 1, 4017, 7200, 2),
(9013, 'SIC', 3404, 3480, 3, 3406, 3483, 4),
(9014, 'SIC', 3241, 2870, 3, 3242, 2873, 4),
(9015, 'SIC', 3301, 3200, 2, 3317, 3261, 4),
(9016, 'SEC', 2568, 5000, 2, 2573, 5031, 4),
(9017, 'NAICS', 1792, 562, 2, 1810, 562991, 5),
(9018, 'SIC', 4312, 60, 1, 3998, 6726, 4),
(9019, 'SIC', 4158, 8050, 3, 4160, 8052, 4),
(9020, 'SIC', 3974, 6400, 2, 3975, 6410, 3),
(9021, 'SEC', 2791, 20, 1, 2293, 2610, 3),
(9022, 'NAICS', 36, 1114, 3, 41, 111421, 5),
(9023, 'SEC', 2794, 52, 1, 2630, 5700, 2),
(9024, 'SIC', 3174, 2650, 3, 3177, 2655, 4),
(9025, 'SIC', 2798, 100, 2, 2819, 179, 4),
(9026, 'SIC', 2813, 170, 3, 2817, 174, 4),
(9027, 'NAICS', 1485, 522, 2, 1509, 522320, 5),
(9028, 'NAICS', 2037, 81, 1, 2060, 81131, 4),
(9029, 'SIC', 4308, 20, 1, 3346, 3322, 4),
(9030, 'SIC', 2909, 1300, 2, 2912, 1320, 3),
(9031, 'NAICS', 226, 2372, 3, 227, 237210, 5),
(9032, 'NAICS', 1403, 511, 2, 1414, 511191, 5),
(9033, 'SIC', 3322, 3270, 3, 3324, 3272, 4),
(9034, 'NAICS', 174, 21311, 4, 176, 213112, 5),
(9035, 'NAICS', 153, 21229, 4, 154, 212291, 5),
(9036, 'NAICS', 1625, 541, 2, 1663, 54143, 4),
(9037, 'NAICS', 1850, 62, 1, 1905, 6231, 3),
(9038, 'NAICS', 1875, 62142, 4, 1874, 621420, 5),
(9039, 'SIC', 3737, 5050, 3, 3739, 5052, 4),
(9040, 'SIC', 4307, 15, 1, 2941, 1521, 4),
(9041, 'SEC', 2791, 20, 1, 2266, 2221, 4),
(9042, 'SIC', 3977, 6500, 2, 3987, 6540, 3),
(9043, 'NAICS', 2, 111, 2, 54, 111992, 5),
(9044, 'NAICS', 1547, 5242, 3, 1551, 524291, 5),
(9045, 'SIC', 4310, 50, 1, 3746, 5074, 4),
(9046, 'SEC', 2640, 5900, 2, 2641, 5910, 3),
(9047, 'SIC', 2798, 100, 2, 2808, 133, 4),
(9048, 'SIC', 4310, 50, 1, 3756, 5090, 3),
(9049, 'NAICS', 1850, 62, 1, 1904, 623, 2),
(9050, 'NAICS', 2037, 81, 1, 2120, 8139, 3),
(9051, 'NAICS', 132, 21, 1, 167, 21239, 4),
(9052, 'NAICS', 2188, 926, 2, 2199, 92615, 4),
(9053, 'SIC', 4308, 20, 1, 3180, 2670, 3),
(9054, 'SEC', 2795, 60, 1, 2666, 6159, 4),
(9055, 'SIC', 2889, 1030, 3, 2890, 1031, 4),
(9056, 'NAICS', 1974, 71212, 4, 1973, 712120, 5),
(9057, 'SIC', 3526, 3700, 2, 3534, 3721, 4),
(9058, 'SEC', 2221, 1300, 2, 2223, 1311, 4),
(9059, 'NAICS', 1863, 62132, 4, 1862, 621320, 5),
(9060, 'NAICS', 1513, 523, 2, 1533, 52399, 4),
(9061, 'SIC', 4308, 20, 1, 3386, 3442, 4),
(9062, 'SIC', 4308, 20, 1, 3344, 3320, 3),
(9063, 'SIC', 2799, 110, 3, 2804, 119, 4),
(9064, 'NAICS', 235, 238, 2, 237, 238110, 5),
(9065, 'NAICS', 1015, 424, 2, 1016, 4241, 3),
(9066, 'SIC', 4308, 20, 1, 3309, 3240, 3),
(9067, 'SIC', 3533, 3720, 3, 3535, 3724, 4),
(9068, 'NAICS', 1725, 56, 1, 1734, 56131, 4),
(9069, 'SIC', 2798, 100, 2, 2805, 130, 3),
(9070, 'SIC', 4313, 70, 1, 4150, 8021, 4),
(9071, 'NAICS', 132, 21, 1, 170, 212393, 5),
(9072, 'SIC', 4314, 90, 1, 4275, 9450, 3),
(9073, 'SIC', 4308, 20, 1, 3390, 3448, 4),
(9074, 'SIC', 4312, 60, 1, 3999, 6730, 3),
(9075, 'SEC', 2284, 2510, 3, 2285, 2511, 4),
(9076, 'SIC', 4312, 60, 1, 3974, 6400, 2),
(9077, 'NAICS', 1851, 621, 2, 1857, 621210, 5),
(9078, 'NAICS', 1990, 7139, 3, 1998, 71394, 4),
(9079, 'SIC', 3496, 3640, 3, 3500, 3645, 4),
(9080, 'NAICS', 1571, 5311, 3, 1577, 53113, 4),
(9081, 'SEC', 2794, 52, 1, 2642, 5912, 4),
(9082, 'SEC', 2791, 20, 1, 2452, 3674, 4),
(9083, 'SEC', 2403, 3500, 2, 2421, 3564, 4),
(9084, 'SIC', 3667, 4700, 2, 3671, 4729, 4),
(9085, 'SEC', 2788, 1, 1, 2212, 700, 2),
(9086, 'SIC', 4313, 70, 1, 4043, 7312, 4),
(9087, 'NAICS', 1015, 424, 2, 1088, 42499, 4),
(9088, 'NAICS', 2166, 923, 2, 2169, 92311, 4),
(9089, 'SIC', 2798, 100, 2, 2818, 175, 4),
(9090, 'SIC', 4017, 7200, 2, 4020, 7212, 4),
(9091, 'SIC', 4310, 50, 1, 3762, 5100, 2),
(9092, 'NAICS', 1056, 42451, 4, 1055, 424510, 5),
(9093, 'SIC', 3272, 3080, 3, 3279, 3087, 4),
(9094, 'SIC', 4192, 8300, 2, 4200, 8361, 4),
(9095, 'NAICS', 932, 4231, 3, 937, 423130, 5),
(9096, 'NAICS', 931, 423, 2, 947, 423310, 5),
(9097, 'NAICS', 1626, 5411, 3, 1632, 541191, 5),
(9098, 'SIC', 4310, 50, 1, 3741, 5063, 4),
(9099, 'NAICS', 244, 23814, 4, 243, 238140, 5),
(9100, 'SIC', 3375, 3420, 3, 3376, 3421, 4),
(9101, 'SIC', 3330, 3290, 3, 3335, 3297, 4),
(9102, 'SIC', 4308, 20, 1, 3396, 3462, 4),
(9103, 'NAICS', 1666, 5415, 3, 1669, 541512, 5),
(9104, 'SEC', 2564, 4950, 3, 2565, 4953, 4),
(9105, 'NAICS', 1569, 53, 1, 1602, 53222, 4),
(9106, 'SEC', 2791, 20, 1, 2254, 2080, 3),
(9107, 'SIC', 4308, 20, 1, 3011, 2053, 4),
(9108, 'SEC', 2795, 60, 1, 2698, 6519, 4),
(9109, 'SIC', 3605, 4100, 2, 3612, 4131, 4),
(9110, 'NAICS', 1804, 5629, 3, 1805, 562910, 5),
(9111, 'SEC', 2476, 3800, 2, 2490, 3842, 4),
(9112, 'SEC', 2791, 20, 1, 2310, 2740, 3),
(9113, 'NAICS', 1402, 51, 1, 1433, 51221, 4),
(9114, 'NAICS', 2014, 72121, 4, 2015, 721211, 5),
(9115, 'SIC', 3576, 3900, 2, 3590, 3953, 4),
(9116, 'SIC', 3480, 3600, 2, 3522, 3692, 4),
(9117, 'SIC', 4313, 70, 1, 4207, 8422, 4),
(9118, 'NAICS', 1419, 512, 2, 1439, 51224, 4),
(9119, 'SIC', 4310, 50, 1, 3735, 5048, 4),
(9120, 'SIC', 3592, 3960, 3, 3593, 3961, 4),
(9121, 'SIC', 4313, 70, 1, 4090, 7532, 4),
(9122, 'NAICS', 1963, 7114, 3, 1965, 71141, 4),
(9123, 'SIC', 2898, 1090, 3, 2900, 1099, 4),
(9124, 'NAICS', 2003, 72, 1, 2019, 72131, 4),
(9125, 'NAICS', 1624, 54, 1, 1635, 54121, 4),
(9126, 'NAICS', 1624, 54, 1, 1710, 541921, 5),
(9127, 'SIC', 2825, 200, 2, 2826, 210, 3),
(9128, 'NAICS', 1672, 5416, 3, 1679, 541620, 5),
(9129, 'SIC', 4311, 52, 1, 3899, 5946, 4),
(9130, 'SIC', 3654, 4500, 2, 3658, 4520, 3),
(9131, 'SIC', 4313, 70, 1, 4117, 7820, 3),
(9132, 'SIC', 2914, 1380, 3, 2917, 1389, 4),
(9133, 'NAICS', 1823, 6114, 3, 1824, 611410, 5),
(9134, 'NAICS', 1850, 62, 1, 1870, 621399, 5),
(9135, 'SIC', 4308, 20, 1, 3083, 2300, 2),
(9136, 'SIC', 3083, 2300, 2, 3099, 2341, 4),
(9137, 'NAICS', 2201, 9271, 3, 2202, 927110, 5),
(9138, 'SIC', 4311, 52, 1, 3886, 5900, 2),
(9139, 'NAICS', 1494, 52219, 4, 1493, 522190, 5),
(9140, 'SIC', 4313, 70, 1, 4232, 8732, 4),
(9141, 'SEC', 2276, 2400, 2, 2280, 2450, 3),
(9142, 'SIC', 4308, 20, 1, 3035, 2092, 4),
(9143, 'NAICS', 1850, 62, 1, 1868, 62139, 4),
(9144, 'SIC', 3903, 5960, 3, 3904, 5961, 4),
(9145, 'SIC', 2848, 710, 3, 2849, 711, 4),
(9146, 'SIC', 3311, 3250, 3, 3315, 3259, 4),
(9147, 'SIC', 4254, 9190, 3, 4255, 9191, 4),
(9148, 'SIC', 4308, 20, 1, 2998, 2037, 4),
(9149, 'SIC', 3419, 3500, 2, 3474, 3590, 3),
(9150, 'NAICS', 1028, 42431, 4, 1027, 424310, 5),
(9151, 'SIC', 4313, 70, 1, 4075, 7380, 3),
(9152, 'SIC', 4305, 1, 1, 2828, 212, 4),
(9153, 'SEC', 2638, 5810, 3, 2639, 5812, 4),
(9154, 'SEC', 2793, 50, 1, 2593, 5120, 3),
(9155, 'SIC', 2884, 1000, 2, 2893, 1044, 4),
(9156, 'SIC', 4305, 1, 1, 2842, 272, 4),
(9157, 'SEC', 2591, 5100, 2, 2595, 5130, 3),
(9158, 'SIC', 3621, 4210, 3, 3625, 4215, 4),
(9159, 'NAICS', 138, 212, 2, 153, 21229, 4),
(9160, 'NAICS', 2151, 9221, 3, 2160, 922150, 5),
(9161, 'SIC', 4313, 70, 1, 4063, 7361, 4),
(9162, 'SIC', 3577, 3910, 3, 3578, 3911, 4),
(9163, 'NAICS', 2199, 92615, 4, 2198, 926150, 5),
(9164, 'SEC', 2796, 70, 1, 2757, 8051, 4),
(9165, 'NAICS', 208, 23611, 4, 212, 236118, 5),
(9166, 'SIC', 4221, 8690, 3, 4222, 8699, 4),
(9167, 'NAICS', 3, 1111, 3, 17, 111191, 5),
(9168, 'SIC', 2982, 2000, 2, 2987, 2020, 3),
(9169, 'SIC', 3214, 2800, 2, 3230, 2840, 3),
(9170, 'SEC', 2722, 7360, 3, 2724, 7363, 4),
(9171, 'SIC', 4308, 20, 1, 3453, 3562, 4),
(9172, 'SIC', 3000, 2040, 3, 3005, 2046, 4),
(9173, 'NAICS', 1726, 561, 2, 1790, 561990, 5),
(9174, 'SIC', 3869, 5700, 2, 3875, 5720, 3),
(9175, 'SIC', 4217, 8650, 3, 4218, 8651, 4),
(9176, 'SIC', 4125, 7900, 2, 4134, 7941, 4),
(9177, 'SEC', 2791, 20, 1, 2485, 3826, 4),
(9178, 'NAICS', 1486, 5221, 3, 1489, 522120, 5),
(9179, 'NAICS', 1843, 61169, 4, 1844, 611691, 5),
(9180, 'NAICS', 2106, 81311, 4, 2105, 813110, 5),
(9181, 'NAICS', 1, 11, 1, 45, 11191, 4),
(9182, 'NAICS', 930, 42, 1, 988, 42373, 4),
(9183, 'NAICS', 2175, 92314, 4, 2174, 923140, 5),
(9184, 'NAICS', 1015, 424, 2, 1039, 42442, 4),
(9185, 'SIC', 4259, 9220, 3, 4260, 9221, 4),
(9186, 'SIC', 3576, 3900, 2, 3600, 3999, 4),
(9187, 'SIC', 4309, 40, 1, 3603, 4011, 4),
(9188, 'SIC', 4002, 6790, 3, 4004, 6794, 4),
(9189, 'SIC', 4308, 20, 1, 3053, 2220, 3),
(9190, 'NAICS', 1480, 52, 1, 1566, 52592, 4),
(9191, 'SEC', 2791, 20, 1, 2503, 3930, 3),
(9192, 'SIC', 4007, 7000, 2, 4015, 7040, 3),
(9193, 'NAICS', 132, 21, 1, 152, 212234, 5),
(9194, 'NAICS', 1726, 561, 2, 1784, 56179, 4),
(9195, 'SIC', 3526, 3700, 2, 3536, 3728, 4),
(9196, 'NAICS', 1419, 512, 2, 1429, 512191, 5),
(9197, 'SEC', 2791, 20, 1, 2505, 3940, 3),
(9198, 'NAICS', 1570, 531, 2, 1588, 53132, 4),
(9199, 'NAICS', 1624, 54, 1, 1688, 54172, 4),
(9200, 'SIC', 3371, 3400, 2, 3384, 3440, 3),
(9201, 'NAICS', 1480, 52, 1, 1494, 52219, 4),
(9202, 'SIC', 4308, 20, 1, 3097, 2339, 4),
(9203, 'NAICS', 2, 111, 2, 51, 11194, 4),
(9204, 'NAICS', 1016, 4241, 3, 1021, 424130, 5),
(9205, 'SIC', 4309, 40, 1, 3693, 4900, 2),
(9206, 'SEC', 2319, 2800, 2, 2334, 2870, 3),
(9207, 'SIC', 3715, 5000, 2, 3723, 5023, 4),
(9208, 'SIC', 3917, 6000, 2, 3925, 6030, 3),
(9209, 'SEC', 2384, 3400, 2, 2394, 3444, 4),
(9210, 'NAICS', 1420, 5121, 3, 1424, 51212, 4),
(9211, 'NAICS', 2135, 92, 1, 2197, 92614, 4),
(9212, 'SEC', 2295, 2620, 3, 2296, 2621, 4),
(9213, 'SIC', 4308, 20, 1, 3167, 2600, 2),
(9214, 'SIC', 3645, 4480, 3, 3648, 4489, 4),
(9215, 'SEC', 2795, 60, 1, 2700, 6531, 4),
(9216, 'NAICS', 1766, 5616, 3, 1768, 561611, 5),
(9217, 'SIC', 3195, 2730, 3, 3197, 2732, 4),
(9218, 'SIC', 3420, 3510, 3, 3421, 3511, 4),
(9219, 'SEC', 2221, 1300, 2, 2224, 1380, 3),
(9220, 'NAICS', 235, 238, 2, 246, 23815, 4),
(9221, 'NAICS', 1640, 5413, 3, 1649, 541350, 5),
(9222, 'SIC', 4305, 1, 1, 2811, 160, 3),
(9223, 'NAICS', 56, 112, 2, 66, 112210, 5),
(9224, 'NAICS', 1689, 5418, 3, 1705, 54189, 4),
(9225, 'NAICS', 1058, 42452, 4, 1057, 424520, 5),
(9226, 'SIC', 4146, 8000, 2, 4173, 8093, 4),
(9227, 'NAICS', 931, 423, 2, 939, 423140, 5),
(9228, 'SEC', 2791, 20, 1, 2409, 3531, 4),
(9229, 'SIC', 2948, 1600, 2, 2951, 1620, 3),
(9230, 'SIC', 4268, 9400, 2, 4276, 9451, 4),
(9231, 'NAICS', 931, 423, 2, 993, 42381, 4),
(9232, 'NAICS', 1708, 54191, 4, 1707, 541910, 5),
(9233, 'SIC', 4256, 9200, 2, 4260, 9221, 4),
(9234, 'NAICS', 2, 111, 2, 35, 111339, 5),
(9235, 'SIC', 3756, 5090, 3, 3757, 5091, 4),
(9236, 'SIC', 4313, 70, 1, 4235, 8740, 3),
(9237, 'NAICS', 2103, 813, 2, 2111, 813219, 5),
(9238, 'SEC', 2796, 70, 1, 2764, 8090, 3),
(9239, 'SIC', 4313, 70, 1, 4041, 7310, 3),
(9240, 'NAICS', 1725, 56, 1, 1811, 562998, 5),
(9241, 'SIC', 2955, 1700, 2, 2973, 1780, 3),
(9242, 'SIC', 3124, 2400, 2, 3137, 2440, 3),
(9243, 'SIC', 3815, 5300, 2, 3817, 5311, 4),
(9244, 'NAICS', 1640, 5413, 3, 1652, 54136, 4),
(9245, 'NAICS', 1480, 52, 1, 1508, 52231, 4),
(9246, 'SEC', 2585, 5080, 3, 2586, 5082, 4),
(9247, 'SIC', 4309, 40, 1, 3679, 4789, 4),
(9248, 'SIC', 3419, 3500, 2, 3461, 3570, 3),
(9249, 'SEC', 2791, 20, 1, 2311, 2741, 4),
(9250, 'SEC', 2458, 3700, 2, 2462, 3714, 4),
(9251, 'SEC', 2791, 20, 1, 2328, 2840, 3),
(9252, 'NAICS', 1754, 56149, 4, 1756, 561492, 5),
(9253, 'NAICS', 1015, 424, 2, 1035, 4244, 3),
(9254, 'NAICS', 1513, 523, 2, 1522, 52314, 4),
(9255, 'NAICS', 1624, 54, 1, 1648, 54134, 4),
(9256, 'NAICS', 1, 11, 1, 80, 112410, 5),
(9257, 'SEC', 2731, 7380, 3, 2732, 7381, 4),
(9258, 'SIC', 4178, 8200, 2, 4179, 8210, 3),
(9259, 'SIC', 3602, 4010, 3, 3603, 4011, 4),
(9260, 'SIC', 3144, 2490, 3, 3145, 2491, 4),
(9261, 'NAICS', 118, 1151, 3, 125, 115116, 5),
(9262, 'NAICS', 1593, 53211, 4, 1595, 532112, 5),
(9263, 'SIC', 3595, 3990, 3, 3600, 3999, 4),
(9264, 'SIC', 4312, 60, 1, 3985, 6530, 3),
(9265, 'SIC', 4312, 60, 1, 3940, 6140, 3),
(9266, 'SIC', 4312, 60, 1, 3990, 6552, 4),
(9267, 'NAICS', 1943, 711, 2, 1955, 711211, 5),
(9268, 'SIC', 3404, 3480, 3, 3408, 3489, 4),
(9269, 'SIC', 3762, 5100, 2, 3782, 5148, 4),
(9270, 'SEC', 2337, 2900, 2, 2338, 2910, 3),
(9271, 'SIC', 2840, 270, 3, 2842, 272, 4),
(9272, 'NAICS', 1778, 56172, 4, 1777, 561720, 5),
(9273, 'NAICS', 2038, 811, 2, 2055, 811212, 5),
(9274, 'SEC', 2796, 70, 1, 2714, 7310, 3),
(9275, 'SEC', 2403, 3500, 2, 2425, 3571, 4),
(9276, 'SIC', 2847, 700, 2, 2854, 724, 4),
(9277, 'NAICS', 2135, 92, 1, 2181, 92412, 4),
(9278, 'SIC', 3180, 2670, 3, 3188, 2678, 4),
(9279, 'SIC', 4305, 1, 1, 2804, 119, 4),
(9280, 'SIC', 3419, 3500, 2, 3454, 3563, 4),
(9281, 'NAICS', 1898, 6222, 3, 1899, 622210, 5),
(9282, 'NAICS', 2071, 812, 2, 2076, 812113, 5),
(9283, 'SIC', 4125, 7900, 2, 4145, 7999, 4),
(9284, 'SIC', 3252, 2900, 2, 3255, 2950, 3),
(9285, 'SIC', 4313, 70, 1, 4128, 7920, 3),
(9286, 'NAICS', 2037, 81, 1, 2130, 81399, 4),
(9287, 'NAICS', 930, 42, 1, 1018, 42411, 4),
(9288, 'SEC', 2794, 52, 1, 2634, 5731, 4),
(9289, 'NAICS', 56, 112, 2, 97, 11299, 4),
(9290, 'SEC', 2539, 4800, 2, 2544, 4822, 4),
(9291, 'SEC', 2796, 70, 1, 2731, 7380, 3),
(9292, 'NAICS', 235, 238, 2, 276, 238990, 5),
(9293, 'SIC', 4277, 9500, 2, 4283, 9532, 4),
(9294, 'SIC', 4208, 8600, 2, 4217, 8650, 3),
(9295, 'NAICS', 1431, 5122, 3, 1434, 512220, 5),
(9296, 'SIC', 4312, 60, 1, 3938, 6110, 3),
(9297, 'NAICS', 1485, 522, 2, 1508, 52231, 4),
(9298, 'NAICS', 1758, 5615, 3, 1759, 561510, 5),
(9299, 'SIC', 2891, 1040, 3, 2892, 1041, 4),
(9300, 'NAICS', 1485, 522, 2, 1494, 52219, 4),
(9301, 'NAICS', 1624, 54, 1, 1676, 541613, 5),
(9302, 'SIC', 4311, 52, 1, 3887, 5910, 3),
(9303, 'NAICS', 1471, 5191, 3, 1474, 519120, 5),
(9304, 'SIC', 4308, 20, 1, 3508, 3661, 4),
(9305, 'SIC', 3762, 5100, 2, 3776, 5142, 4),
(9306, 'NAICS', 1747, 56143, 4, 1749, 561439, 5),
(9307, 'NAICS', 2, 111, 2, 13, 11115, 4),
(9308, 'SIC', 4311, 52, 1, 3872, 5713, 4),
(9309, 'SIC', 4308, 20, 1, 3546, 3764, 4),
(9310, 'NAICS', 205, 23, 1, 264, 23832, 4),
(9311, 'SEC', 2796, 70, 1, 2762, 8080, 3),
(9312, 'SIC', 3480, 3600, 2, 3517, 3677, 4),
(9313, 'SEC', 2403, 3500, 2, 2430, 3579, 4),
(9314, 'SIC', 4306, 10, 1, 2933, 1475, 4),
(9315, 'NAICS', 1, 11, 1, 113, 114119, 5),
(9316, 'NAICS', 1591, 532, 2, 1618, 532490, 5),
(9317, 'NAICS', 1, 11, 1, 57, 1121, 3),
(9318, 'SEC', 2591, 5100, 2, 2598, 5150, 3),
(9319, 'SIC', 4125, 7900, 2, 4137, 7951, 4),
(9320, 'SIC', 4313, 70, 1, 4233, 8733, 4),
(9321, 'NAICS', 1725, 56, 1, 1767, 56161, 4),
(9322, 'NAICS', 1894, 622, 2, 1896, 622110, 5),
(9323, 'NAICS', 1624, 54, 1, 1717, 54199, 4),
(9324, 'NAICS', 2037, 81, 1, 2082, 81221, 4),
(9325, 'NAICS', 2037, 81, 1, 2078, 812191, 5),
(9326, 'SIC', 3681, 4810, 3, 3682, 4812, 4)
RETURNING industry_level_id;

INSERT INTO industry_structure (industry_structure_id, industry_classification, depth, level_name) VALUES
(1, 'SIC', 1, 'Division'),
(2, 'SIC', 2, 'Major Group'),
(3, 'SIC', 3, 'Industry Group'),
(4, 'SIC', 4, 'Industry'),
(5, 'SEC', 1, 'Division'),
(6, 'SEC', 2, 'Major Group'),
(7, 'SEC', 3, 'Industry Group'),
(8, 'SEC', 4, 'Industry'),
(49, 'NAICS', 1, 'Economic Sector'),
(50, 'NAICS', 2, 'Subsector'),
(51, 'NAICS', 3, 'Industry Group'),
(52, 'NAICS', 4, 'NAICS Industry'),
(53, 'NAICS', 5, 'National Industry')
RETURNING industry_structure_id;


--
-- Name: accession_element_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY accession_element ALTER COLUMN accession_element_id SET DEFAULT nextval('accession_element_accession_element_id_seq'::regclass);


--
-- Name: accession_document_association_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY accession_document_association
    ADD CONSTRAINT accession_document_association_pkey PRIMARY KEY (accession_document_association_id);


--
-- Name: accession_element_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY accession_element
    ADD CONSTRAINT accession_element_pkey PRIMARY KEY (accession_element_id);


--
-- Name: accession_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY accession
    ADD CONSTRAINT accession_pkey PRIMARY KEY (accession_id);


--
-- Name: attribute_value_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY attribute_value
    ADD CONSTRAINT attribute_value_pkey PRIMARY KEY (attribute_value_id);


--
-- Name: context_aug_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY context_aug
    ADD CONSTRAINT context_aug_pkey PRIMARY KEY (context_id);


--
-- Name: context_dimension_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY context_dimension
    ADD CONSTRAINT context_dimension_pkey PRIMARY KEY (context_dimension_id);


--
-- Name: context_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY context
    ADD CONSTRAINT context_pkey PRIMARY KEY (context_id);


--
-- Name: custom_arcrole_type_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY custom_arcrole_type
    ADD CONSTRAINT custom_arcrole_type_pkey PRIMARY KEY (custom_arcrole_type_id);


--
-- Name: custom_arcrole_used_on_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY custom_arcrole_used_on
    ADD CONSTRAINT custom_arcrole_used_on_pkey PRIMARY KEY (custom_arcrole_used_on_id);


--
-- Name: custom_role_type_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY custom_role_type
    ADD CONSTRAINT custom_role_type_pkey PRIMARY KEY (custom_role_type_id);


--
-- Name: document_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY document
    ADD CONSTRAINT document_pkey PRIMARY KEY (document_id);


--
-- Name: element_attribute_association_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY element_attribute_value_association
    ADD CONSTRAINT element_attribute_association_pkey PRIMARY KEY (element_attribute_value_association_id);


--
-- Name: element_attribute_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY element_attribute
    ADD CONSTRAINT element_attribute_pkey PRIMARY KEY (element_attribute_id);


--
-- Name: element_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY element
    ADD CONSTRAINT element_pkey PRIMARY KEY (element_id);


--
-- Name: entity_name_history_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY entity_name_history
    ADD CONSTRAINT entity_name_history_pkey PRIMARY KEY (entity_name_history_id);


--
-- Name: entity_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY entity
    ADD CONSTRAINT entity_pkey PRIMARY KEY (entity_id);


--
-- Name: enumeration_arcrole_cycles_allowed_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY enumeration_arcrole_cycles_allowed
    ADD CONSTRAINT enumeration_arcrole_cycles_allowed_pkey PRIMARY KEY (enumeration_arcrole_cycles_allowed_id);


--
-- Name: enumeration_element_balance_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY enumeration_element_balance
    ADD CONSTRAINT enumeration_element_balance_pkey PRIMARY KEY (enumeration_element_balance_id);


--
-- Name: enumeration_element_period_type_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY enumeration_element_period_type
    ADD CONSTRAINT enumeration_element_period_type_pkey PRIMARY KEY (enumeration_element_period_type_id);


--
-- Name: enumeration_unit_measure_location_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY enumeration_unit_measure_location
    ADD CONSTRAINT enumeration_unit_measure_location_pkey PRIMARY KEY (enumeration_unit_measure_location_id);


--
-- Name: fact_aug_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY fact_aug
    ADD CONSTRAINT fact_aug_pkey PRIMARY KEY (fact_id);


--
-- Name: fact_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY fact
    ADD CONSTRAINT fact_pkey PRIMARY KEY (fact_id);


--
-- Name: industry_level_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY industry_level
    ADD CONSTRAINT industry_level_pkey PRIMARY KEY (industry_level_id);


--
-- Name: industry_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY industry
    ADD CONSTRAINT industry_pkey PRIMARY KEY (industry_id);


--
-- Name: industry_structure_industry_classification_depth_key; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY industry_structure
    ADD CONSTRAINT industry_structure_industry_classification_depth_key UNIQUE (industry_classification, depth);


--
-- Name: industry_structure_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY industry_structure
    ADD CONSTRAINT industry_structure_pkey PRIMARY KEY (industry_structure_id);


--
-- Name: namespace_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY namespace
    ADD CONSTRAINT namespace_pkey PRIMARY KEY (namespace_id);


--
-- Name: network_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY network
    ADD CONSTRAINT network_pkey PRIMARY KEY (network_id);


--
-- Name: pk_label_resouce; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY label_resource
    ADD CONSTRAINT pk_label_resouce PRIMARY KEY (resource_id);


--
-- Name: qname_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY qname
    ADD CONSTRAINT qname_pkey PRIMARY KEY (qname_id);


--
-- Name: query_log_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY query_log
    ADD CONSTRAINT query_log_pkey PRIMARY KEY (query_log_id);


--
-- Name: reference_part_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY reference_part
    ADD CONSTRAINT reference_part_pkey PRIMARY KEY (reference_part_id);


--
-- Name: reference_part_type_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY reference_part_type
    ADD CONSTRAINT reference_part_type_pkey PRIMARY KEY (reference_part_type_id);


--
-- Name: reference_resource_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY reference_resource
    ADD CONSTRAINT reference_resource_pkey PRIMARY KEY (reference_resource_id);


--
-- Name: relationship_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY relationship
    ADD CONSTRAINT relationship_pkey PRIMARY KEY (relationship_id);


--
-- Name: resource_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY resource
    ADD CONSTRAINT resource_pkey PRIMARY KEY (resource_id);


--
-- Name: sic_code_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY sic_code
    ADD CONSTRAINT sic_code_pkey PRIMARY KEY (sic_code_id);


--
-- Name: taxonomy_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY taxonomy
    ADD CONSTRAINT taxonomy_pkey PRIMARY KEY (taxonomy_id);


--
-- Name: taxonomy_version_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY taxonomy_version
    ADD CONSTRAINT taxonomy_version_pkey PRIMARY KEY (taxonomy_version_id);


--
-- Name: unit_measure_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY unit_measure
    ADD CONSTRAINT unit_measure_pkey PRIMARY KEY (unit_measure_id);


--
-- Name: unit_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY unit
    ADD CONSTRAINT unit_pkey PRIMARY KEY (unit_id);


--
-- Name: uri_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY uri
    ADD CONSTRAINT uri_pkey PRIMARY KEY (uri_id);


--
-- Name: used_on_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY custom_role_used_on
    ADD CONSTRAINT used_on_pkey PRIMARY KEY (custom_role_used_on_id);

--
-- Name: accession_document_association_index01; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX accession_document_association_index01 ON accession_document_association USING btree (accession_id, document_id);


--
-- Name: accession_document_association_index02; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX accession_document_association_index02 ON accession_document_association USING btree (document_id, accession_id);


--
-- Name: accession_element_index01; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX accession_element_index01 ON accession_element USING btree (accession_id, element_id);


--
-- Name: accession_element_index02; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX accession_element_index02 ON accession_element USING btree (element_id, accession_id);


--
-- Name: accession_index01; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX accession_index01 ON accession USING btree (filing_accession_number);


--
-- Name: accession_index02; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX accession_index02 ON accession USING btree (standard_industrial_classification);


--
-- Name: accession_index03; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX accession_index03 ON accession USING btree (accepted_timestamp DESC);


--
-- Name: accession_index04; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX accession_index04 ON accession USING btree (entity_id);


--
-- Name: accession_timestamp_idx01; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX accession_timestamp_idx01 ON accession_timestamp USING btree (accession_id);


--
-- Name: attribute_value_index01; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX attribute_value_index01 ON attribute_value USING btree (qname_id, text_value);


--
-- Name: conext_dimension_index03; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX conext_dimension_index03 ON context_dimension USING btree (dimension_qname_id, member_qname_id);


--
-- Name: content_aug_idx04; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX content_aug_idx04 ON context_aug USING btree (fiscal_period, fiscal_year, context_id);


--
-- Name: context_aug_idx01; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX context_aug_idx01 ON context_aug USING btree (fiscal_year, fiscal_period, context_id);


--
-- Name: context_aug_idx02; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX context_aug_idx02 ON context_aug USING btree (fiscal_year, context_id);


--
-- Name: context_aug_idx03; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX context_aug_idx03 ON context_aug USING btree (fiscal_period, context_id);


--
-- Name: context_dimension_index01; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX context_dimension_index01 ON context_dimension USING btree (context_id);


--
-- Name: context_dimension_index02; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX context_dimension_index02 ON context_dimension USING btree (member_qname_id, dimension_qname_id);


--
-- Name: context_dimension_index04; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX context_dimension_index04 ON context_dimension USING btree (member_qname_id);


--
-- Name: context_dimension_index05; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX context_dimension_index05 ON context_dimension USING btree (dimension_qname_id);


--
-- Name: context_dimension_index06; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX context_dimension_index06 ON context_dimension USING btree (dimension_qname_id, context_id);


--
-- Name: context_index01; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX context_index01 ON context USING btree (accession_id);


--
-- Name: context_index02; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX context_index02 ON context USING btree (accession_id, context_id);


--
-- Name: context_index03; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX context_index03 ON context USING btree (context_id, accession_id);


--
-- Name: custom_arcrole_type_index01; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX custom_arcrole_type_index01 ON custom_arcrole_type USING btree (document_id, uri_id);


--
-- Name: custom_role_used_on_ix; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX custom_role_used_on_ix ON custom_role_used_on USING btree (custom_role_type_id);


--
-- Name: document_index01; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX document_index01 ON document USING btree (document_uri);


--
-- Name: element_attribute_association_index01; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX element_attribute_association_index01 ON element_attribute_value_association USING btree (element_id, attribute_value_id);


--
-- Name: element_attribute_index01; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX element_attribute_index01 ON element_attribute USING btree (element_id, attribute_qname_id);


--
-- Name: element_index01; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX element_index01 ON element USING btree (document_id, qname_id);


--
-- Name: element_index02; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX element_index02 ON element USING btree (qname_id);


--
-- Name: element_index03; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX element_index03 ON element USING btree (qname_id, element_id);


--
-- Name: entity_index01; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX entity_index01 ON entity USING btree (authority_scheme, entity_code);


--
-- Name: entity_index02; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX entity_index02 ON entity USING btree (entity_code);


--
-- Name: entity_name_history_index01; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX entity_name_history_index01 ON entity_name_history USING btree (entity_id, accession_id);


--
-- Name: entity_ts_index03; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX entity_ts_index03 ON entity USING gin (to_tsvector('english'::regconfig, (entity_name)::text));


--
-- Name: fact_aug_index01; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX fact_aug_index01 ON fact_aug USING btree (fact_hash, fact_id);


--
-- Name: fact_aug_index02; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX fact_aug_index02 ON fact_aug USING btree (fact_id, fact_hash);


--
-- Name: fact_aug_index03; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX fact_aug_index03 ON fact_aug USING btree (fact_id, ultimus_index);


--
-- Name: fact_aug_index04; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX fact_aug_index04 ON fact_aug USING btree (ultimus_index, fact_id);


--
-- Name: fact_aug_index05; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX fact_aug_index05 ON fact_aug USING btree (calendar_hash, fact_id);


--
-- Name: fact_aug_index06; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX fact_aug_index06 ON fact_aug USING btree (fact_id, uom, ultimus_index, calendar_ultimus_index);


--
-- Name: fact_index01; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX fact_index01 ON fact USING btree (accession_id, element_id);


--
-- Name: fact_index02; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX fact_index02 ON fact USING btree (element_id);


--
-- Name: fact_index03; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX fact_index03 ON fact USING btree (unit_id);


--
-- Name: fact_index04; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX fact_index04 ON fact USING btree (context_id);


--
-- Name: fact_index05; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX fact_index05 ON fact USING btree (accession_id);


--
-- Name: fact_index06; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX fact_index06 ON fact USING btree (element_id, context_id);


--
-- Name: fact_index07; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX fact_index07 ON fact USING btree (context_id, element_id);


--
-- Name: fact_index08; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX fact_index08 ON fact USING btree (element_id, fiscal_year, fiscal_period, ultimus_index, uom);


--
-- Name: fact_index09; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX fact_index09 ON fact USING btree (element_id, calendar_year, calendar_period, calendar_ultimus_index, uom);


--
-- Name: fact_ts_index03; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX fact_ts_index03 ON fact USING gin (to_tsvector('english'::regconfig, fact_value));


--
-- Name: idx_context_xml_id; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX idx_context_xml_id ON context USING btree (accession_id, context_xml_id);


--
-- Name: industry_industry_classification_industry_code_idx; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX industry_industry_classification_industry_code_idx ON industry USING btree (industry_classification, industry_code);


--
-- Name: industry_level_index01; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX industry_level_index01 ON industry_level USING btree (industry_classification, ancestor_id, descendant_id);


--
-- Name: industry_level_index02; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX industry_level_index02 ON industry_level USING btree (industry_classification, descendant_id, ancestor_id);


--
-- Name: label_resource_index01; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX label_resource_index01 ON label_resource USING btree (resource_id);


--
-- Name: label_resource_ts_index02; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX label_resource_ts_index02 ON label_resource USING gin (to_tsvector('english'::regconfig, label));


--
-- Name: namespace_idx01; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX namespace_idx01 ON namespace USING btree (uri);


--
-- Name: namespace_idx02; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX namespace_idx02 ON namespace USING btree (is_base);


--
-- Name: network_index01; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX network_index01 ON network USING btree (accession_id);


--
-- Name: network_index02; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX network_index02 ON network USING btree (arcrole_uri_id);


--
-- Name: qname_index01; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX qname_index01 ON qname USING btree (qname_id, namespace);


--
-- Name: qname_index02; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX qname_index02 ON qname USING btree (local_name, namespace);


--
-- Name: qname_index03; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX qname_index03 ON qname USING btree (lower((local_name)::text));


--
-- Name: qname_index04; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX qname_index04 ON qname USING btree (namespace, qname_id);


--
-- Name: qname_index05; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX qname_index05 ON qname USING btree (namespace, local_name);


--
-- Name: qname_index07; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX qname_index07 ON qname USING btree (lower((local_name)::text) varchar_pattern_ops);


--
-- Name: qname_namespace_localname; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX qname_namespace_localname ON qname USING btree (namespace, local_name);


--
-- Name: qname_ts_index06; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX qname_ts_index06 ON qname USING gin (to_tsvector('english'::regconfig, regexp_replace((local_name)::text, '([A-Z])'::text, ' \1'::text, 'g'::text)));


--
-- Name: relationship_element_resource_index01; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX relationship_element_resource_index01 ON relationship USING btree (from_element_id, to_resource_id);


--
-- Name: relationship_element_resource_index02; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX relationship_element_resource_index02 ON relationship USING btree (to_resource_id, from_element_id);


--
-- Name: relationship_from_res_ix; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX relationship_from_res_ix ON relationship USING btree (from_resource_id);


--
-- Name: relationship_index01; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX relationship_index01 ON relationship USING btree (from_element_id);


--
-- Name: relationship_index02; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX relationship_index02 ON relationship USING btree (to_element_id, network_id);


--
-- Name: relationship_index03; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX relationship_index03 ON relationship USING btree (network_id, from_element_id, to_element_id);


--
-- Name: relationship_to_res_ix; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX relationship_to_res_ix ON relationship USING btree (to_resource_id);


--
-- Name: resource_index01; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX resource_index01 ON resource USING btree (document_id, document_line_number, document_column_number);


--
-- Name: resource_index02; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX resource_index02 ON resource USING btree (role_uri_id);


--
-- Name: unit_accession_id_unit_xml_id; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX unit_accession_id_unit_xml_id ON unit USING btree (accession_id, unit_xml_id);


--
-- Name: unit_index01; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX unit_index01 ON unit USING btree (accession_id, unit_xml_id);


--
-- Name: unit_measure_index01; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX unit_measure_index01 ON unit_measure USING btree (unit_id);


--
-- Name: uri_index01; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX uri_index01 ON uri USING btree (uri);


/*********** Arelle block out these Triggers and Constraints

--
-- Name: a1_accession_complete_restatement_period_index; Type: TRIGGER; Schema: public; Owner: postgres
--

--CREATE TRIGGER a1_accession_complete_restatement_period_index AFTER INSERT OR DELETE OR UPDATE ON accession FOR EACH ROW EXECUTE PROCEDURE accession_restatement_period_index();


--
-- Name: accession_complete_delete; Type: TRIGGER; Schema: public; Owner: postgres
--

--CREATE TRIGGER accession_complete_delete AFTER DELETE ON accession FOR EACH ROW EXECUTE PROCEDURE accession_complete();


--
-- Name: accession_complete_insert; Type: TRIGGER; Schema: public; Owner: postgres
--

--CREATE TRIGGER accession_complete_insert AFTER INSERT ON accession FOR EACH ROW WHEN ((new.is_complete = true)) EXECUTE PROCEDURE accession_complete();


--
-- Name: accession_complete_update; Type: TRIGGER; Schema: public; Owner: postgres
--

--CREATE TRIGGER accession_complete_update AFTER UPDATE ON accession FOR EACH ROW WHEN (((COALESCE(old.is_complete, false) = false) AND (new.is_complete = true))) EXECUTE PROCEDURE accession_complete();


--
-- Name: accession_timestamp_add; Type: TRIGGER; Schema: public; Owner: postgres
--

--CREATE TRIGGER accession_timestamp_add AFTER INSERT ON accession FOR EACH ROW EXECUTE PROCEDURE accession_timestamp_add();

--
-- Name: fact_aug_trigger_delete; Type: TRIGGER; Schema: public; Owner: postgres
--

--CREATE TRIGGER fact_aug_trigger_delete BEFORE DELETE ON fact FOR EACH ROW EXECUTE PROCEDURE fact_aug_trigger();


--
-- Name: accession_element_accession_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY accession_element
    ADD CONSTRAINT accession_element_accession_id_fkey FOREIGN KEY (accession_id) REFERENCES accession(accession_id);


--
-- Name: accession_element_element_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY accession_element
    ADD CONSTRAINT accession_element_element_id_fkey FOREIGN KEY (element_id) REFERENCES element(element_id);


--
-- Name: element_reference_resource; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY reference_resource
    ADD CONSTRAINT element_reference_resource FOREIGN KEY (element_id) REFERENCES element(element_id);


--
-- Name: entity_name_history_accession_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY entity_name_history
    ADD CONSTRAINT entity_name_history_accession_id_fkey FOREIGN KEY (accession_id) REFERENCES accession(accession_id);


--
-- Name: entity_name_history_entity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY entity_name_history
    ADD CONSTRAINT entity_name_history_entity_id_fkey FOREIGN KEY (entity_id) REFERENCES entity(entity_id);


--
-- Name: fact_aug_fact_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY fact_aug
    ADD CONSTRAINT fact_aug_fact_id_fkey FOREIGN KEY (fact_id) REFERENCES fact(fact_id) ON DELETE CASCADE;


--
-- Name: fk_accession_entity; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

-- Arelle note: entities are not populated for reference by accession
--ALTER TABLE ONLY accession
--    ADD CONSTRAINT fk_accession_entity FOREIGN KEY (entity_id) REFERENCES entity(entity_id);


--
-- Name: fk_ada_accession; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY accession_document_association
    ADD CONSTRAINT fk_ada_accession FOREIGN KEY (accession_id) REFERENCES accession(accession_id);


--
-- Name: fk_ada_document; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY accession_document_association
    ADD CONSTRAINT fk_ada_document FOREIGN KEY (document_id) REFERENCES document(document_id);


--
-- Name: fk_arcrole_cycles; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY custom_arcrole_type
    ADD CONSTRAINT fk_arcrole_cycles FOREIGN KEY (cycles_allowed) REFERENCES enumeration_arcrole_cycles_allowed(enumeration_arcrole_cycles_allowed_id);


--
-- Name: fk_attribute_value_qname; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY attribute_value
    ADD CONSTRAINT fk_attribute_value_qname FOREIGN KEY (qname_id) REFERENCES qname(qname_id);


--
-- Name: fk_context_accession; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY context
    ADD CONSTRAINT fk_context_accession FOREIGN KEY (accession_id) REFERENCES accession(accession_id);


--
-- Name: fk_context_dimension_dimension; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY context_dimension
    ADD CONSTRAINT fk_context_dimension_dimension FOREIGN KEY (context_id) REFERENCES context(context_id);


--
-- Name: fk_context_dimension_dimension_qname; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY context_dimension
    ADD CONSTRAINT fk_context_dimension_dimension_qname FOREIGN KEY (dimension_qname_id) REFERENCES qname(qname_id);


--
-- Name: fk_context_dimension_member_qname; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY context_dimension
    ADD CONSTRAINT fk_context_dimension_member_qname FOREIGN KEY (member_qname_id) REFERENCES qname(qname_id);


--
-- Name: fk_context_dimension_typed_qname; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY context_dimension
    ADD CONSTRAINT fk_context_dimension_typed_qname FOREIGN KEY (typed_qname_id) REFERENCES qname(qname_id);


--
-- Name: fk_custom_arcrole_type_document; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY custom_arcrole_type
    ADD CONSTRAINT fk_custom_arcrole_type_document FOREIGN KEY (document_id) REFERENCES document(document_id);


--
-- Name: fk_custom_role_type; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY custom_role_type
    ADD CONSTRAINT fk_custom_role_type FOREIGN KEY (document_id) REFERENCES document(document_id);


--
-- Name: fk_custom_role_type_uri; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY custom_role_type
    ADD CONSTRAINT fk_custom_role_type_uri FOREIGN KEY (uri_id) REFERENCES uri(uri_id);


--
-- Name: fk_eav_av; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY element_attribute_value_association
    ADD CONSTRAINT fk_eav_av FOREIGN KEY (attribute_value_id) REFERENCES attribute_value(attribute_value_id);


--
-- Name: fk_eav_element; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY element_attribute_value_association
    ADD CONSTRAINT fk_eav_element FOREIGN KEY (element_id) REFERENCES element(element_id);


--
-- Name: fk_element_attribute_attribute_def; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY element_attribute
    ADD CONSTRAINT fk_element_attribute_attribute_def FOREIGN KEY (attribute_qname_id) REFERENCES qname(qname_id);


--
-- Name: fk_element_attribute_element; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY element_attribute
    ADD CONSTRAINT fk_element_attribute_element FOREIGN KEY (element_id) REFERENCES element(element_id);


--
-- Name: fk_element_balance; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY element
    ADD CONSTRAINT fk_element_balance FOREIGN KEY (balance_id) REFERENCES enumeration_element_balance(enumeration_element_balance_id);


--
-- Name: fk_element_datatype_qname; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY element
    ADD CONSTRAINT fk_element_datatype_qname FOREIGN KEY (datatype_qname_id) REFERENCES qname(qname_id);


--
-- Name: fk_element_document; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY element
    ADD CONSTRAINT fk_element_document FOREIGN KEY (document_id) REFERENCES document(document_id);


--
-- Name: fk_element_period_type; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY element
    ADD CONSTRAINT fk_element_period_type FOREIGN KEY (period_type_id) REFERENCES enumeration_element_period_type(enumeration_element_period_type_id);


--
-- Name: fk_element_qname; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY element
    ADD CONSTRAINT fk_element_qname FOREIGN KEY (qname_id) REFERENCES qname(qname_id);


--
-- Name: fk_element_sg_qname; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY element
    ADD CONSTRAINT fk_element_sg_qname FOREIGN KEY (substitution_group_qname_id) REFERENCES qname(qname_id);


--
-- Name: fk_element_xbrl_base_datatype_qname; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY element
    ADD CONSTRAINT fk_element_xbrl_base_datatype_qname FOREIGN KEY (xbrl_base_datatype_qname_id) REFERENCES qname(qname_id);


--
-- Name: fk_fact_accession; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY fact
    ADD CONSTRAINT fk_fact_accession FOREIGN KEY (accession_id) REFERENCES accession(accession_id);


--
-- Name: fk_fact_context; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY fact
    ADD CONSTRAINT fk_fact_context FOREIGN KEY (context_id) REFERENCES context(context_id);


--
-- Name: fk_fact_element; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY fact
    ADD CONSTRAINT fk_fact_element FOREIGN KEY (element_id) REFERENCES element(element_id);


--
-- Name: fk_fact_unit; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY fact
    ADD CONSTRAINT fk_fact_unit FOREIGN KEY (unit_id) REFERENCES unit(unit_id);


--
-- Name: fk_network_accession; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY network
    ADD CONSTRAINT fk_network_accession FOREIGN KEY (accession_id) REFERENCES accession(accession_id);


--
-- Name: fk_network_arc_qname; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY network
    ADD CONSTRAINT fk_network_arc_qname FOREIGN KEY (arc_qname_id) REFERENCES qname(qname_id);


--
-- Name: fk_network_arcrole_uri; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY network
    ADD CONSTRAINT fk_network_arcrole_uri FOREIGN KEY (arcrole_uri_id) REFERENCES uri(uri_id);


--
-- Name: fk_network_link_qname; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY network
    ADD CONSTRAINT fk_network_link_qname FOREIGN KEY (extended_link_qname_id) REFERENCES qname(qname_id);


--
-- Name: fk_network_link_role_uri; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY network
    ADD CONSTRAINT fk_network_link_role_uri FOREIGN KEY (extended_link_role_uri_id) REFERENCES uri(uri_id);


--
-- Name: fk_reference_part_qname; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY reference_part
    ADD CONSTRAINT fk_reference_part_qname FOREIGN KEY (qname_id) REFERENCES qname(qname_id);


--
-- Name: fk_reference_part_resource; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY reference_part
    ADD CONSTRAINT fk_reference_part_resource FOREIGN KEY (resource_id) REFERENCES resource(resource_id);


--
-- Name: fk_rel_from_element; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY relationship
    ADD CONSTRAINT fk_rel_from_element FOREIGN KEY (from_element_id) REFERENCES element(element_id);


--
-- Name: fk_rel_from_resource; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY relationship
    ADD CONSTRAINT fk_rel_from_resource FOREIGN KEY (from_resource_id) REFERENCES resource(resource_id);


--
-- Name: fk_rel_network; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY relationship
    ADD CONSTRAINT fk_rel_network FOREIGN KEY (network_id) REFERENCES network(network_id);


--
-- Name: fk_rel_to_element; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY relationship
    ADD CONSTRAINT fk_rel_to_element FOREIGN KEY (to_element_id) REFERENCES element(element_id);


--
-- Name: fk_rel_to_resource; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY relationship
    ADD CONSTRAINT fk_rel_to_resource FOREIGN KEY (to_resource_id) REFERENCES resource(resource_id);


--
-- Name: fk_resource_document; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY resource
    ADD CONSTRAINT fk_resource_document FOREIGN KEY (document_id) REFERENCES document(document_id);


--
-- Name: fk_resource_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY label_resource
    ADD CONSTRAINT fk_resource_id FOREIGN KEY (resource_id) REFERENCES resource(resource_id);


--
-- Name: fk_resource_qname; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY resource
    ADD CONSTRAINT fk_resource_qname FOREIGN KEY (qname_id) REFERENCES qname(qname_id);


--
-- Name: fk_resource_role_uri; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY resource
    ADD CONSTRAINT fk_resource_role_uri FOREIGN KEY (role_uri_id) REFERENCES uri(uri_id);


--
-- Name: fk_unit_accession; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY unit
    ADD CONSTRAINT fk_unit_accession FOREIGN KEY (accession_id) REFERENCES accession(accession_id);


--
-- Name: fk_unit_measure_location; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY unit_measure
    ADD CONSTRAINT fk_unit_measure_location FOREIGN KEY (location_id) REFERENCES enumeration_unit_measure_location(enumeration_unit_measure_location_id);


--
-- Name: fk_unit_measure_qname; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY unit_measure
    ADD CONSTRAINT fk_unit_measure_qname FOREIGN KEY (qname_id) REFERENCES qname(qname_id);


--
-- Name: fk_unit_measure_unit; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY unit_measure
    ADD CONSTRAINT fk_unit_measure_unit FOREIGN KEY (unit_id) REFERENCES unit(unit_id);


--
-- Name: fk_used_on_custom_arcrole_type; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY custom_arcrole_used_on
    ADD CONSTRAINT fk_used_on_custom_arcrole_type FOREIGN KEY (custom_arcrole_type_id) REFERENCES custom_arcrole_type(custom_arcrole_type_id);


--
-- Name: fk_used_on_custom_role_type; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY custom_role_used_on
    ADD CONSTRAINT fk_used_on_custom_role_type FOREIGN KEY (custom_role_type_id) REFERENCES custom_role_type(custom_role_type_id);


--
-- Name: fk_used_on_qname; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY custom_role_used_on
    ADD CONSTRAINT fk_used_on_qname FOREIGN KEY (qname_id) REFERENCES qname(qname_id);


--
-- Name: fk_used_on_qname; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY custom_arcrole_used_on
    ADD CONSTRAINT fk_used_on_qname FOREIGN KEY (qname_id) REFERENCES qname(qname_id);


--
-- Name: fkey_context_context_aug; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY context_aug
    ADD CONSTRAINT fkey_context_context_aug FOREIGN KEY (context_id) REFERENCES context(context_id) ON DELETE CASCADE;


--
-- Name: namespace_taxonomy_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

--ALTER TABLE ONLY namespace
--    ADD CONSTRAINT namespace_taxonomy_version_id_fkey FOREIGN KEY (taxonomy_version_id) --REFERENCES taxonomy_version(taxonomy_version_id);


--
-- Name: role_type_reference_resource; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY reference_resource
    ADD CONSTRAINT role_type_reference_resource FOREIGN KEY (extended_link_role_id) REFERENCES uri(uri_id);


--
-- Name: role_type_reference_resource_2; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY reference_resource
    ADD CONSTRAINT role_type_reference_resource_2 FOREIGN KEY (resource_role_id) REFERENCES uri(uri_id);


--
-- Name: role_type_role_type_label; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY uri
    ADD CONSTRAINT role_type_role_type_label FOREIGN KEY (uri_id) REFERENCES uri(uri_id);


--
-- Name: taxonomy_version_taxonomy_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY taxonomy_version
    ADD CONSTRAINT taxonomy_version_taxonomy_id_fkey FOREIGN KEY (taxonomy_id) REFERENCES taxonomy(taxonomy_id);

********* end of removed triggers and constraints *****/

--
-- PostgreSQL database dump complete
--

