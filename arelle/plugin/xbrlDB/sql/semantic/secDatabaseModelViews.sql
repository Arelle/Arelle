-- SEC Database Model Views (based on Abstract Model Sematic SQL schema)
-- See COPYRIGHT.md for copyright information.

DROP VIEW IF EXISTS sec_filing;
DROP VIEW IF EXISTS sec_entity;
DROP VIEW IF EXISTS sec_element;

CREATE VIEW sec_filing AS
	SELECT f.reference_number AS cik, f.form_type AS form_type, f.filing_number AS accession_number, f.filing_date AS filing_date,
	       -- filing date changed is not loaded for now
	       -- assistant director (from RSS feed)
	       f.creation_software AS creation_software, f.entry_url AS filing_url,
	       d.namespace AS standard_namespace
	FROM filing f
	JOIN report r on f.filing_id = r.filing_id
	LEFT JOIN document d on d.document_id = 
	   (CASE WHEN r.agency_schema_doc_id IS NOT null
	         THEN r.agency_schema_doc_id
	         ELSE r.standard_schema_doc_id
	    END);
	    
CREATE VIEW sec_entity AS
	SELECT f.reference_number AS cik, f.filing_number AS accession_number, 
	       e.legal_entity_number AS lei, e.name as registrant_name,
	       e.phys_addr1 AS biz_addr1, e.phys_addr2 AS biz_addr2,
	       e.phys_city AS biz_city, e.phys_state AS biz_state, e.phys_zip as biz_zip,
	       e.phys_country AS biz_country, e.phone AS biz_phone,
	       e.legal_state AS state_of_incorporation,
	       e.standard_industry_code AS sic,
	       e.trading_symbol AS ticker,
	       e.fiscal_year_end AS fiscal_year_end_date,
	       e.filer_category AS filer_category,
	       e.public_float AS public_float
	       -- f.fiscal_year AS fiscal_year_focus,
	       -- f.fiscal_period AS fiscal_period_focus
	FROM entity e
	JOIN filing f on f.entity_id = e.entity_id;
	
CREATE VIEW sec_element AS
	SELECT distinct -- without distinct would repeat elements by number of facts having element
	       f.reference_number AS cik, f.filing_number AS accession_number, 
	       tdp.table_code AS financial_statement,
	       (a.document_id = r.report_schema_doc_id) AS is_extension,
	       lbl.value AS label,
	       -- documentation
	       a.name AS name,
	       dt.name AS data_type,
	       dt.base_type as xbrl_type,
	       a.period_type as period_type
	FROM filing f
	JOIN report r ON f.filing_id = r.filing_id
	JOIN data_point dp ON dp.report_id = r.report_id
	JOIN aspect a ON a.aspect_id = dp.aspect_id
	LEFT JOIN data_type dt ON dt.data_type_id = a.datatype_id
	LEFT JOIN table_data_points tdp ON tdp.datapoint_id = dp.datapoint_id
	LEFT JOIN relationship_set rs ON rs.document_id = r.report_schema_doc_id AND
	      rs.arc_role = 'http://www.xbrl.org/2003/arcrole/concept-label'
	LEFT JOIN relationship r_lbl ON r_lbl.relationship_set_id = rs.relationship_set_id AND
	      r_lbl.from_id = a.aspect_id
	JOIN resource lbl ON r_lbl.to_id = lbl.resource_id AND
	      lbl.role = 'http://www.xbrl.org/2003/role/label' AND
	      lbl.xml_lang = 'en-US'
	      
CREATE VIEW sec_fact AS
	SELECT -- same as element but without distinct and with value stuff
	       f.reference_number AS cik, f.filing_number AS accession_number, 
	       tdp.table_code AS financial_statement,
	       (a.document_id = r.report_schema_doc_id) AS is_extension,
	       lbl.value AS label,
	       -- document label
	       a.name AS name,
	       dt.name AS data_type,
	       dt.base_type as xbrl_type,
	       a.period_type as period_type,
	       dp.decimals_value AS decimals,
	       dp.value AS value,
	       dp.is_nil AS is_nil,
	       (dp.decimals_value = 'INF') AS is_inf
	FROM filing f
	JOIN report r ON f.filing_id = r.filing_id
	LEFT JOIN relationship_set rs ON rs.document_id = r.report_schema_doc_id AND
	      rs.arc_role = 'http://www.xbrl.org/2003/arcrole/concept-label'
	JOIN data_point dp ON dp.report_id = r.report_id
	JOIN aspect a ON a.aspect_id = dp.aspect_id
		LEFT JOIN data_type dt ON dt.data_type_id = a.datatype_id
	LEFT JOIN table_data_points tdp ON tdp.object_id = dp.datapoint_id
	LEFT JOIN relationship r_lbl ON r_lbl.relationship_set_id = rs.relationship_set_id AND
	      r_lbl.from_id = a.aspect_id
	JOIN resource lbl ON r_lbl.to_id = lbl.resource_id AND
	      lbl.role = 'http://www.xbrl.org/2003/role/label' AND
	      lbl.xml_lang = 'en-US'