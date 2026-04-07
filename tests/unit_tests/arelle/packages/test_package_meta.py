from arelle.packages.package_meta import PackageMeta

_PACKAGE_CONFIG = {
    "URL": "tests/resources/packages/example.zip",
    "description": "Example taxonomy package.",
    "entryPoints": {
        "Example entry point #1": [
            (
                "/example/all1.xsd",
                "https://www.example.com/all1.xsd",
                "Example entry point."
            )
        ],
        "Example entry point #2": [
            (
                "https://www.example.com/all2.xsd",
                "https://www.example.com/all2.xsd",
                "Example entry point with URL instead of file path."
            )
        ]
    },
    "fileDate": "2025-05-20T19:45:47 UTC",
    "identifier": "https://www.example.com/all",
    "license": "The IFRS Taxonomy - Terms and Conditions",
    "manifestName": "META-INF/taxonomyPackage.xml",
    "name": "Example taxonomy",
    "publicationDate": "2024-12-31",
    "publisher": "Example publisher",
    "publisherCountry": "NL",
    "publisherURL": "https://www.example.com/publisher",
    "remappings": {
        "https://www.example.com/2024-12-31/": "/example/2024-12-31/"
    },
    "status": "enabled",
    "supersededTaxonomyPackages": [],
    "version": "31 december 2024",
    "versioningReports": [
        "https://www.example.com/versioning1.xml",
        "https://www.example.com/versioning2.xml",
    ]
}


def test_parse_package_config_empty():
    """
    Test that PackageMeta is correctly parsed from minimal config.
    """
    package_meta = PackageMeta.from_config({})

    assert package_meta.description is None
    assert len(package_meta.entry_points) == 0
    assert package_meta.file_date is None
    assert package_meta.identifier is None
    assert package_meta.license is None
    assert package_meta.manifest_name is None
    assert package_meta.name is None
    assert package_meta.publication_date is None
    assert package_meta.publisher is None
    assert package_meta.publisher_country is None
    assert package_meta.publisher_url is None
    assert len(package_meta.remappings) == 0
    assert package_meta.status is None
    assert len(package_meta.superseded_taxonomy_packages) == 0
    assert len(package_meta.url) == 0
    assert package_meta.version is None
    assert len(package_meta.versioning_reports) == 0


def test_parse_package_config_full():
    """
    Test that PackageMeta is correctly parsed from maximal config.
    """
    package_meta = PackageMeta.from_config(_PACKAGE_CONFIG)
    assert package_meta.description == "Example taxonomy package."
    assert package_meta.entry_points == {
        "Example entry point #1": frozenset([
            (
                "/example/all1.xsd",
                "https://www.example.com/all1.xsd",
                "Example entry point."
            )
        ]),
        "Example entry point #2":  frozenset([
            (
                "https://www.example.com/all2.xsd",
                "https://www.example.com/all2.xsd",
                "Example entry point with URL instead of file path."
            )
        ])
    }
    assert package_meta.file_date == "2025-05-20T19:45:47 UTC"
    assert package_meta.identifier == "https://www.example.com/all"
    assert package_meta.license == "The IFRS Taxonomy - Terms and Conditions"
    assert package_meta.manifest_name == "META-INF/taxonomyPackage.xml"
    assert package_meta.name == "Example taxonomy"
    assert package_meta.publication_date == "2024-12-31"
    assert package_meta.publisher == "Example publisher"
    assert package_meta.publisher_country == "NL"
    assert package_meta.publisher_url == "https://www.example.com/publisher"
    assert package_meta.remappings == {
        "https://www.example.com/2024-12-31/": "/example/2024-12-31/"
    }
    assert package_meta.status == "enabled"
    assert package_meta.superseded_taxonomy_packages == frozenset()
    assert package_meta.url == "tests/resources/packages/example.zip"
    assert package_meta.version == "31 december 2024"
    assert package_meta.versioning_reports == frozenset({
        "https://www.example.com/versioning1.xml",
        "https://www.example.com/versioning2.xml",
    })
