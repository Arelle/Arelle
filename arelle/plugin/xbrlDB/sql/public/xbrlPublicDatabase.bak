--
-- PostgreSQL database dump
--

SET statement_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = off;
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

CREATE TABLE fact (
    fact_id integer DEFAULT nextval('seq_fact'::regclass) NOT NULL,
    accession_id integer NOT NULL,
    context_id integer NOT NULL,
    unit_id integer,
    element_id integer NOT NULL,
    effective_value numeric,
    fact_value text,
    xml_id character varying(2048),
    precision_value integer,
    decimals_value integer,
    is_precision_infinity boolean DEFAULT false NOT NULL,
    is_decimals_infinity boolean DEFAULT false NOT NULL,
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

CREATE INDEX qname_ts_index06 ON qname USING gin (to_tsvector('english'::regconfig, regexp_replace((local_name)::text, '([A-Z])'::text, ' \\1'::text, 'g'::text)));


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

ALTER TABLE ONLY accession
    ADD CONSTRAINT fk_accession_entity FOREIGN KEY (entity_id) REFERENCES entity(entity_id);


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

ALTER TABLE ONLY namespace
    ADD CONSTRAINT namespace_taxonomy_version_id_fkey FOREIGN KEY (taxonomy_version_id) REFERENCES taxonomy_version(taxonomy_version_id);


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


--
-- PostgreSQL database dump complete
--

