from __future__ import annotations

from pathlib import Path

from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteAssetConfig

# https://taxonomies.xbrl.org/taxonomy/68
LEI_2018_11_01 = ConformanceSuiteAssetConfig.public_taxonomy_package(
    Path('lei-taxonomy-CR-2018-11-01.zip'),
    public_download_url='http://www.xbrl.org/taxonomy/int/lei/lei-taxonomy-CR-2018-11-01.zip',
)
# https://taxonomies.xbrl.org/taxonomy/87
LEI_2020_07_02 = ConformanceSuiteAssetConfig.public_taxonomy_package(
    Path('lei-taxonomy-REC-2020-07-02.zip'),
    public_download_url='https://www.xbrl.org/taxonomy/int/lei/lei-taxonomy-REC-2020-07-02.zip',
)
ESEF_PACKAGES: dict[int, list[ConformanceSuiteAssetConfig]] = {
    2017: [
        # https://www.esma.europa.eu/document/esma-esef-taxonomy-2017
        ConformanceSuiteAssetConfig.public_taxonomy_package(
            Path('esef_taxonomy_2017.zip'),
            public_download_url='https://www.esma.europa.eu/sites/default/files/library/esef_taxonomy_2017.zip',
        ),
        # https://www.ifrs.org/issued-standards/ifrs-taxonomy/ifrs-taxonomy-2017/
        ConformanceSuiteAssetConfig.public_taxonomy_package(
            Path('IFRST_2017-03-09.zip'),
            public_download_url='http://xbrl.ifrs.org/taxonomy/2017-03-09/IFRST_2017-03-09.zip',
        ),
        LEI_2018_11_01,
    ],
    2019: [
        # https://www.esma.europa.eu/document/esma-esef-taxonomy-2019
        ConformanceSuiteAssetConfig.public_taxonomy_package(
            Path('esef_taxonomy_2019.zip'),
            public_download_url='https://www.esma.europa.eu/sites/default/files/library/esef_taxonomy_2019.zip',
        ),
        # https://www.ifrs.org/issued-standards/ifrs-taxonomy/ifrs-taxonomy-2019/
        ConformanceSuiteAssetConfig.public_taxonomy_package(
            Path('IFRST_2019-03-27.zip'),
            public_download_url='https://www.ifrs.org/content/dam/ifrs/standards/taxonomy/ifrs-taxonomies/IFRST_2019-03-27.zip',
        ),
        LEI_2018_11_01,
    ],
    2020: [
        # https://www.esma.europa.eu/document/esma-esef-taxonomy-2020
        ConformanceSuiteAssetConfig.public_taxonomy_package(
            Path('esef_taxonomy_2020.zip'),
            public_download_url='https://www.esma.europa.eu/sites/default/files/library/esef_taxonomy_2020.zip',
        ),
        # https://www.ifrs.org/issued-standards/ifrs-taxonomy/ifrs-taxonomy-2020/
        ConformanceSuiteAssetConfig.public_taxonomy_package(
            Path('IFRST_2020-03-16.zip'),
            public_download_url='https://www.ifrs.org/content/dam/ifrs/standards/taxonomy/ifrs-taxonomies/IFRST_2020-03-16.zip',
        ),
        LEI_2020_07_02,
    ],
    2021: [
        # https://www.esma.europa.eu/document/esma-esef-taxonomy-2021
        ConformanceSuiteAssetConfig.public_taxonomy_package(
            Path('esef_taxonomy_2021.zip'),
            public_download_url='https://www.esma.europa.eu/sites/default/files/library/esef_taxonomy_2021.zip',
        ),
        # https://www.ifrs.org/issued-standards/ifrs-taxonomy/ifrs-taxonomy-2021/
        ConformanceSuiteAssetConfig.public_taxonomy_package(
            Path('IFRST_2021-03-24.zip'),
            public_download_url='https://www.ifrs.org/content/dam/ifrs/standards/taxonomy/ifrs-taxonomies/IFRST_2021-03-24.zip',
        ),
        LEI_2020_07_02,
    ],
    2022: [
        # https://www.esma.europa.eu/document/esef-taxonomy-2022
        ConformanceSuiteAssetConfig.public_taxonomy_package(
            Path('esef_taxonomy_2022_v1.1.zip'),
            public_download_url='https://www.esma.europa.eu/sites/default/files/2023-12/esef_taxonomy_2022_v1.1.zip',
        ),
        # https://www.ifrs.org/issued-standards/ifrs-taxonomy/ifrs-accounting-taxonomy-2022/
        ConformanceSuiteAssetConfig.public_taxonomy_package(
            Path('IFRSAT-2022-03-24.zip'),
            public_download_url='https://www.ifrs.org/content/dam/ifrs/standards/taxonomy/ifrs-taxonomies/IFRSAT-2022-03-24.zip',
        ),
        LEI_2020_07_02,
    ],
    2024: [
        # https://www.esma.europa.eu/document/esef-taxonomy-2024
        ConformanceSuiteAssetConfig.public_taxonomy_package(
            Path('esef_taxonomy_2024.zip'),
            public_download_url='https://www.esma.europa.eu/sites/default/files/2025-01/esef_taxonomy_2024.zip',
        ),
        # https://www.ifrs.org/issued-standards/ifrs-taxonomy/ifrs-accounting-taxonomy-2024/
        ConformanceSuiteAssetConfig.public_taxonomy_package(
            Path('IFRSAT-2024-03-27_29.08.24.zip'),
            public_download_url='https://www.ifrs.org/content/dam/ifrs/standards/taxonomy/ifrs-taxonomies/IFRSAT-2024-03-27_29.08.24.zip'
        ),
        LEI_2020_07_02,
    ],
}

NL_BASE = ConformanceSuiteAssetConfig.public_taxonomy_package(Path('nltaxonomie-nl-20240326.zip'))
NL_PACKAGES: dict[str, list[ConformanceSuiteAssetConfig]] = {
    'NT16': [
        ConformanceSuiteAssetConfig.public_taxonomy_package(
            Path('NT16_20220803_Taxonomie_SBRlight.zip'),
            public_download_url='https://www.sbr-nl.nl/sites/default/files/bestanden/taxonomie/NT16_20220803%20Taxonomie%20%28SBRlight%29.zip',
        ),
        NL_BASE,
    ],
    'NT17': [
        ConformanceSuiteAssetConfig.public_taxonomy_package(
            Path('NT17_20230811_Taxonomie_SBRLight.zip'),
            public_download_url='https://www.sbr-nl.nl/sites/default/files/bestanden/taxonomie/NT17_20230811%20Taxonomie%20SBRLight.zip'
        ),
        NL_BASE,
    ],
    'NT18': [
        ConformanceSuiteAssetConfig.public_taxonomy_package(
            Path('NT18_20240126_Taxonomie_SBRLight.zip'),
            public_download_url='https://www.sbr-nl.nl/sites/default/files/bestanden/taxonomie/NT18_20240126%20Taxonomie%20%28SBRLight%29.zip',
        ),
        NL_BASE,
    ],
    'NT19': [
        ConformanceSuiteAssetConfig.public_taxonomy_package(
            Path('NT19_20241209_Taxonomie_SBRLight.zip'),
            public_download_url='https://www.sbr-nl.nl/sites/default/files/bestanden/taxonomie/NT19_20241209%20Taxonomie%28SBRlight%29.zip',
        ),
        NL_BASE,
    ],
}
