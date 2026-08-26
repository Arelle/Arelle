const initializeInterfaceComparisons = () => {
  document
    .querySelectorAll("[data-interface-comparison]")
    .forEach((comparison) => {
      const tabs = [...comparison.querySelectorAll('[role="tab"]')];

      const activate = (tab, focus) => {
        tabs.forEach((other) => {
          const selected = other === tab;
          other.ariaSelected = selected;
          other.tabIndex = selected ? 0 : -1;
          document.getElementById(other.getAttribute("aria-controls")).hidden =
            !selected;
        });
        if (focus) tab.focus();
      };

      tabs.forEach((tab, index) => {
        tab.addEventListener("click", () => activate(tab, true));
        tab.addEventListener("keydown", (event) => {
          const targetIndex = {
            ArrowLeft: index - 1,
            ArrowRight: index + 1,
            Home: 0,
            End: tabs.length - 1,
          }[event.key];
          if (targetIndex === undefined) {
            return;
          }

          const next = tabs[(targetIndex + tabs.length) % tabs.length];
          event.preventDefault();
          activate(next, true);
        });
      });

      if (tabs[0]) activate(tabs[0]);
    });
};

if (document.readyState === "loading") {
  document.addEventListener(
    "readystatechange",
    initializeInterfaceComparisons,
    { once: true },
  );
} else {
  initializeInterfaceComparisons();
}
