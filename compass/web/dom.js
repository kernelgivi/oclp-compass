/** DOM helpers keep imported names, notes, and report text out of HTML parsers. */
export const $ = (id) => document.getElementById(id);

export function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined && text !== null) element.textContent = String(text);
  if (className) element.className = className;
  return element;
}

export function externalLink(label, url, className) {
  const link = node("a", label, className);
  link.href = url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  return link;
}

export function download(filename, content, mime) {
  const url = URL.createObjectURL(new Blob([content], { type: mime }));
  const link = node("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function options(select, items, selected) {
  select.replaceChildren(
    ...items.map(([value, label]) => {
      const option = node("option", label);
      option.value = String(value);
      return option;
    })
  );
  if (items.some(([value]) => String(value) === String(selected))) select.value = String(selected);
}

export function signed(value) {
  return `${value > 0 ? "+" : ""}${value}`;
}

export const metricDescriptions = {
  smoothness: {
    title: "Estimated smoothness",
    description:
      "A heuristic estimate of responsiveness based on the model profile, memory, boot drive, macOS overhead, and graphics patching. The CPU model and GPU names are displayed for review; the estimate does not measure their actual performance. Higher values mean the policy expects less overhead, not a measured speed or frame rate.",
  },
  app_recency: {
    title: "OS recency",
    description:
      "A preference for newer macOS releases. Newer releases may satisfy more current app OS requirements, but this score is not an app compatibility database or a statement about current security-update coverage. Check the minimum OS build, CPU instructions, GPU features, and vendor support for the app versions you need.",
  },
  maintenance: {
    title: "Maintenance ease",
    description:
      "An estimate of patching burden. Native installations generally need fewer interventions; OCLP installations and graphics root patches require more attention after updates. This is not a security rating, and the stock graphics assessment is not a complete inventory of wireless or other required patches.",
  },
  score: {
    title: "Weighted fit",
    description:
      "The selected priority combines estimated smoothness, OS recency, and maintenance ease. A score is a preference index out of 100. It is not a probability of successful installation. Hard exclusions always take precedence over the score.",
  },
};
