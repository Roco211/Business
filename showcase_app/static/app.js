const navButtons = Array.from(document.querySelectorAll(".sidebar-nav button"));
const sections = navButtons.map((button) => document.getElementById(button.dataset.target)).filter(Boolean);

navButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const target = document.getElementById(button.dataset.target);
    if (!target) return;
    target.scrollIntoView({ behavior: "smooth", block: "start" });
  });
});

const observer = new IntersectionObserver(
  (entries) => {
    const visible = entries.filter((entry) => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
    if (!visible) return;
    navButtons.forEach((button) => {
      button.classList.toggle("active", button.dataset.target === visible.target.id);
    });
  },
  { rootMargin: "-20% 0px -55% 0px", threshold: [0.2, 0.4, 0.6] }
);

sections.forEach((section) => observer.observe(section));
