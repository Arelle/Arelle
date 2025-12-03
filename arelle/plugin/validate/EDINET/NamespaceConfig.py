"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations


class NamespaceConfig:
    def __init__(self) -> None:
        self.jpcrpEsr = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp-esr/2024-11-01/jpcrp-esr_cor"
        self.jpcrp = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2024-11-01/jpcrp_cor"
        self.jpcrpSbr = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp-sbr/2024-11-01/jpcrp-sbr_cor"
        self.jpctl = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpctl/2024-11-01/jpctl_cor"
        self.jpdei = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/2013-08-31/jpdei_cor"
        self.jpigp = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpigp/2024-11-01/jpigp_cor"
        self.jplvh = "http://disclosure.edinet-fsa.go.jp/taxonomy/jplvh/2024-11-01/jplvh_cor"
        self.jppfs = "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2024-11-01/jppfs_cor"
        self.jpspsEsr = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpsps-esr/2024-11-01/jpsps-esr_cor"
        self.jpspsSbr = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpsps-sbr/2024-11-01/jpsps-sbr_cor"
        self.jpsps = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpsps/2024-11-01/jpsps_cor"
        self.jptoi = "http://disclosure.edinet-fsa.go.jp/taxonomy/jptoi/2024-11-01/jptoi_cor"
        self.jptooPst = "http://disclosure.edinet-fsa.go.jp/taxonomy/jptoo-pst/2024-11-01/jptoo-pst_cor"
        self.jptooToa = "http://disclosure.edinet-fsa.go.jp/taxonomy/jptoo-toa/2024-11-01/jptoo-toa_cor"
        self.jptooTon = "http://disclosure.edinet-fsa.go.jp/taxonomy/jptoo-ton/2024-11-01/jptoo-ton_cor"
        self.jptooTor = "http://disclosure.edinet-fsa.go.jp/taxonomy/jptoo-tor/2024-11-01/jptoo-tor_cor"
        self.jptooWto = "http://disclosure.edinet-fsa.go.jp/taxonomy/jptoo-wto/2024-11-01/jptoo-wto_cor"

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
