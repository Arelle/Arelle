from pathlib import Path

import regex as re


class TestPluginImports:
    def test_pluginsAreNotReferencedUsingAbsoluteImports(self):
        """
        While absolute imports for plugins 'from arelle.plugin import X' work when
        running Arelle from source, they do not when run from frozen builds.
        """
        projectSrc = Path(__file__).parent.parent.parent.parent.parent / "arelle"
        arelleModules = projectSrc.rglob("*.py")

        assert arelleModules, "Test failed to discover Arelle modules."

        absolutePluginImport = re.compile(r"(?<!['\"])arelle\.plugin(?!['\"])")

        modulesImportingPluginsFromRoot = []
        for mod in arelleModules:
            with open(mod, 'r', encoding='utf-8') as f:
                for line in f:
                    if absolutePluginImport.search(line):
                        modulesImportingPluginsFromRoot.append(str(mod.relative_to(projectSrc.parent)))
                        break

        assert not modulesImportingPluginsFromRoot, "Modules import plugins using absolute paths."
