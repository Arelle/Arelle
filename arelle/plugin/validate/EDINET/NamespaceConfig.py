"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from arelle.plugin.validate.EDINET.DisclosureSystems import DISCLOSURE_SYSTEM_RELEASE_DATES


class NamespaceConfig:
    def __init__(self, disclosureSystemName: str | None) -> None:
        assert (disclosureSystemName is not None and
                disclosureSystemName in DISCLOSURE_SYSTEM_RELEASE_DATES), \
            f"Invalid EDINET disclosure system: {disclosureSystemName}"
        release_date = DISCLOSURE_SYSTEM_RELEASE_DATES[disclosureSystemName]
        self.jpcrpEsr = f"http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp-esr/{release_date}/jpcrp-esr_cor"
        self.jpcrp = f"http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/{release_date}/jpcrp_cor"
        self.jpcrpSbr = f"http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp-sbr/{release_date}/jpcrp-sbr_cor"
        self.jpctl = f"http://disclosure.edinet-fsa.go.jp/taxonomy/jpctl/{release_date}/jpctl_cor"
        self.jpigp = f"http://disclosure.edinet-fsa.go.jp/taxonomy/jpigp/{release_date}/jpigp_cor"
        self.jplvh = f"http://disclosure.edinet-fsa.go.jp/taxonomy/jplvh/{release_date}/jplvh_cor"
        self.jppfs = f"http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/{release_date}/jppfs_cor"
        self.jpspsEsr = f"http://disclosure.edinet-fsa.go.jp/taxonomy/jpsps-esr/{release_date}/jpsps-esr_cor"
        self.jpspsSbr = f"http://disclosure.edinet-fsa.go.jp/taxonomy/jpsps-sbr/{release_date}/jpsps-sbr_cor"
        self.jpsps = f"http://disclosure.edinet-fsa.go.jp/taxonomy/jpsps/{release_date}/jpsps_cor"
        self.jptoi = f"http://disclosure.edinet-fsa.go.jp/taxonomy/jptoi/{release_date}/jptoi_cor"
        self.jptooPst = f"http://disclosure.edinet-fsa.go.jp/taxonomy/jptoo-pst/{release_date}/jptoo-pst_cor"
        self.jptooToa = f"http://disclosure.edinet-fsa.go.jp/taxonomy/jptoo-toa/{release_date}/jptoo-toa_cor"
        self.jptooTon = f"http://disclosure.edinet-fsa.go.jp/taxonomy/jptoo-ton/{release_date}/jptoo-ton_cor"
        self.jptooTor = f"http://disclosure.edinet-fsa.go.jp/taxonomy/jptoo-tor/{release_date}/jptoo-tor_cor"
        self.jptooWto = f"http://disclosure.edinet-fsa.go.jp/taxonomy/jptoo-wto/{release_date}/jptoo-wto_cor"

        self.jpdei = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/2013-08-31/jpdei_cor"

        self._namespaceMap = {
            "jpcrp-esr_cor": self.jpcrpEsr,
            "jpcrp-sbr_cor": self.jpcrpSbr,
            "jpcrp_cor": self.jpcrp,
            "jpctl_cor": self.jpctl,
            "jpdei_cor": self.jpdei,
            "jpigp_cor": self.jpigp,
            "jplvh_cor": self.jplvh,
            "jppfs_cor": self.jppfs,
            "jpsps_cor": self.jpsps,
            "jpsps-esr_cor": self.jpspsEsr,
            "jpsps-sbr_cor": self.jpspsSbr,
            "jptoi_cor": self.jptoi,
            "jptoo-pst_cor": self.jptooPst,
            "jptoo-toa_cor": self.jptooToa,
            "jptoo-ton_cor": self.jptooTon,
            "jptoo-tor_cor": self.jptooTor,
            "jptoo-wto_cor": self.jptooWto,
        }

    def get(self, prefix: str) -> str | None:
        """get namespace URI for prefix"""
        return self._namespaceMap.get(prefix)
