/* A static method explorer. All displayed values come from the build catalog. */
(() => {
  "use strict";
  const app = document.getElementById("explorer");
  if (!app) return;

  const list = document.getElementById("methods");
  const search = document.getElementById("method-search");
  const client = document.getElementById("client-filter");
  const group = document.getElementById("group-filter");
  const count = document.getElementById("method-count");
  const labels = { query: "READ", mutation: "WRITE", auth: "AUTH", local: "LOCAL", typed: "TYPED", graphql: "GQL" };
  const groups = ["Accounts", "Transactions", "Budgets", "Goals", "Cashflow", "Investments", "Authentication", "Other"];
  const panels = ["Parameters", "Request", "Response", "Schema"];
  let methods = [];

  function el(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }

  function note(text) { return el("p", text, "note"); }

  function codeBlock(value, language, title) {
    const text = language === "json" ? JSON.stringify(value, null, 2) : String(value);
    const box = el("div", undefined, "code-block");
    box.append(el("div", title || language, "code-label"));
    const copy = el("button", "Copy", "copy");
    copy.type = "button";
    copy.setAttribute("aria-label", `Copy ${title || language}`);
    copy.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(text);
        copy.textContent = "Copied";
      } catch (_) {
        const selection = window.getSelection();
        const range = document.createRange();
        range.selectNodeContents(code);
        selection.removeAllRanges();
        selection.addRange(range);
        copy.textContent = "Select + copy";
      }
      setTimeout(() => { copy.textContent = "Copy"; }, 1800);
    });
    const pre = el("pre");
    const code = el("code");
    if (language === "json") {
      const tokens = /("(?:\\.|[^"\\])*"\s*:?)|\b(true|false|null)\b|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g;
      let last = 0;
      for (const match of text.matchAll(tokens)) {
        code.append(document.createTextNode(text.slice(last, match.index)));
        const kind = match[1] ? (match[1].trimEnd().endsWith(":") ? "key" : "string") : match[2] ? "literal" : "number";
        code.append(el("span", match[0], `json-${kind}`));
        last = match.index + match[0].length;
      }
      code.append(document.createTextNode(text.slice(last)));
    } else code.textContent = text;
    pre.append(code);
    box.append(copy, pre);
    return box;
  }

  function table(headers, rows) {
    const wrap = el("div", undefined, "table-wrap");
    const grid = el("table");
    const head = el("thead");
    const heading = el("tr");
    for (const title of headers) {
      const cell = el("th", title);
      cell.scope = "col";
      heading.append(cell);
    }
    head.append(heading);
    const body = el("tbody");
    for (const cells of rows) {
      const row = el("tr");
      for (const content of cells) {
        const cell = el("td");
        if (content instanceof Node) cell.append(content);
        else cell.textContent = content == null ? "—" : String(content);
        row.append(cell);
      }
      body.append(row);
    }
    grid.append(head, body);
    wrap.append(grid);
    return wrap;
  }

  function disclosure(title, content) {
    const details = el("details", undefined, "extra");
    details.append(el("summary", title), content);
    return details;
  }

  function schemaRows(schema, path = "$", rows = [], root = schema, seen = []) {
    if (!schema) return rows;
    if (schema.$ref) {
      if (seen.includes(schema.$ref)) return rows;
      const target = schema.$ref.split("/").slice(1).reduce((value, key) => value?.[key], root);
      if (target) return schemaRows(target, path, rows, root, [...seen, schema.$ref]);
    }
    const type = schema.type || (schema.properties ? "object" : schema.anyOf ? schema.anyOf.map(item => item.type || "unknown").join(" | ") : "not declared");
    const displayType = schema.description === "Python datetime attribute." ? "datetime" : Array.isArray(type) ? type.join(" | ") : type;
    rows.push([el("code", path, "schema-field"), el("span", displayType, "schema-type")]);
    for (const [key, value] of Object.entries(schema.properties || {})) schemaRows(value, path === "$" ? key : `${path}.${key}`, rows, root, seen);
    if (schema.items && typeof schema.items === "object") schemaRows(schema.items, `${path}[]`, rows, root, seen);
    if (schema.additionalProperties && typeof schema.additionalProperties === "object") schemaRows(schema.additionalProperties, `${path}.*`, rows, root, seen);
    for (const choice of schema.anyOf || []) {
      if (choice.$ref || choice.properties || choice.items) schemaRows(choice, path, rows, root, seen);
    }
    return rows;
  }

  function renderPanel(method, name) {
    const panel = el("div", undefined, "panel");
    if (name === "Parameters") {
      panel.append(codeBlock(method.signature, "python", "Signature"));
      if (!method.parameters.length) panel.append(note("No parameters."));
      else panel.append(table(["Name", "Type", "Description", "Default"], method.parameters.map(param => {
        const nameCell = el("div");
        nameCell.append(el("code", param.name, "parameter-name"), el("span", param.required ? "required" : "optional", param.required ? "required" : "optional"));
        return [nameCell, el("code", param.type || "not annotated"), el("span", param.description || "—", "parameter-description"), param.required ? "—" : el("code", String(param.default))];
      })));
    }
    if (name === "Request") {
      panel.append(note("Python examples assume an authenticated client named mm."));
      panel.append(codeBlock(method.python_example, "python", "Python call"));
      if (method.request_body) {
        panel.append(el("h3", "Request body"), note("POST https://api.monarch.com/graphql · application/json"));
        const body = { operationName: method.request_body.operationName, variables: method.request_body.variables, query: method.request_body.query };
        panel.append(codeBlock(body, "json", "GraphQL request body"));
      } else if (method.graphql) {
        panel.append(note("The client constructs this GraphQL request. A complete JSON body example is not available for this method."));
      } else {
        panel.append(note(method.kind === "local" ? "This method runs locally; it has no HTTP request body." : "Use the Python call above. This method does not expose a single GraphQL request body."));
      }
      if (method.graphql_variables?.length) panel.append(disclosure("GraphQL variables", table(["Variable", "Declared type", "Required"], method.graphql_variables.map(variable => [el("code", variable.name), el("code", variable.type), variable.required ? "yes" : "no"]))));
      if (method.graphql) panel.append(disclosure("GraphQL document", codeBlock(method.graphql, "graphql", "GraphQL")));
    }
    if (name === "Response") {
      const type = el("p", "Python return: ", "return-type");
      type.append(el("code", method.return_type || "not annotated"));
      panel.append(type);
      const hasExample = method.response_example !== null && method.response_example !== undefined;
      if (hasExample) {
        panel.append(note(method.response_note || "Illustrative response example."));
        panel.append(codeBlock(method.response_example, "json", method.client === "TypedMonarchMoney" ? "Model data example" : "Python result · JSON view"));
      } else if (["None", "NoneType"].includes(method.return_type)) {
        panel.append(note("Returns None. There is no response value."));
      } else {
        panel.append(note(method.response_note || "No verified response example is available yet. See Schema for known fields."));
        if (method.response_fields?.length) panel.append(table(["Selected response field"], method.response_fields.map(field => [el("code", typeof field === "string" ? field : field.path)])));
      }
    }
    if (name === "Schema") {
      if (method.response_schema) {
        panel.append(note(method.response_schema.description || method.response_note || "Derived from available source and examples; not a complete remote API contract."));
        panel.append(table(["Field", "Type"], schemaRows(method.response_schema)));
        panel.append(disclosure("JSON Schema", codeBlock(method.response_schema, "json", "JSON Schema")));
      } else if (method.response_fields?.length) {
        panel.append(note("Fields selected by the query. The repository does not declare their scalar types, list cardinality, or nullability."));
        panel.append(table(["Field", "Type"], method.response_fields.map(field => [el("code", typeof field === "string" ? field : field.path), "not declared"])));
      } else panel.append(note(method.response_note || "No response field schema is declared for this method."));
      if (method.response_schema && method.response_fields?.length) panel.append(disclosure("All fields selected by the query", table(["Field"], method.response_fields.map(field => [el("code", typeof field === "string" ? field : field.path)]))));
    }
    return panel;
  }

  function openPanel(card, method, selected, updateHash = true) {
    const body = card.querySelector(".method-body");
    body.replaceChildren();
    const tabs = el("div", undefined, "tab-list");
    tabs.setAttribute("role", "tablist");
    tabs.setAttribute("aria-label", `${method.name} documentation`);
    for (const name of panels) {
      const button = el("button", name);
      button.type = "button";
      button.id = `${method.id}-tab-${name.toLowerCase()}`;
      button.setAttribute("role", "tab");
      button.setAttribute("aria-selected", String(name === selected));
      button.setAttribute("aria-controls", `${method.id}-panel`);
      button.tabIndex = name === selected ? 0 : -1;
      button.addEventListener("click", () => {
        openPanel(card, method, name);
        document.getElementById(button.id).focus({ preventScroll: true });
      });
      button.addEventListener("keydown", event => {
        if (!["ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key)) return;
        event.preventDefault();
        const index = panels.indexOf(name);
        const next = event.key === "Home" ? 0 : event.key === "End" ? 3 : (index + (event.key === "ArrowRight" ? 1 : 3)) % 4;
        openPanel(card, method, panels[next]);
        document.getElementById(`${method.id}-tab-${panels[next].toLowerCase()}`).focus();
      });
      tabs.append(button);
    }
    const content = renderPanel(method, selected);
    content.id = `${method.id}-panel`;
    content.setAttribute("role", "tabpanel");
    content.setAttribute("aria-labelledby", `${method.id}-tab-${selected.toLowerCase()}`);
    const links = el("div", undefined, "method-links");
    const permalink = el("a", "Link to method");
    permalink.href = `#${method.id}/${selected.toLowerCase()}`;
    const source = el("a", "Source ↗");
    source.href = `${app.dataset.repo}/blob/main/${method.source_path}#L${method.source_line}`;
    links.append(permalink, source);
    body.append(tabs, content, links);
    card.dataset.panel = selected;
    if (updateHash) history.replaceState(null, "", `#${method.id}/${selected.toLowerCase()}`);
  }

  function cardFor(method) {
    const card = el("details", undefined, `method kind-${method.kind}`);
    card.id = method.id;
    const summary = el("summary");
    summary.append(el("span", labels[method.kind] || "METHOD", "kind-label"), el("span", method.name, "method-name"), el("span", method.summary, "method-summary"));
    card.append(summary, el("div", undefined, "method-body"));
    card.addEventListener("toggle", () => {
      if (card.open && !card.dataset.panel) openPanel(card, method, "Response", false);
    });
    return card;
  }

  function render() {
    const query = search.value.toLowerCase().trim();
    const selected = methods.filter(method => method.client === client.value && (!group.value || method.group === group.value) && method.searchText.includes(query));
    count.textContent = `${selected.length} methods`;
    document.getElementById("typed-note").hidden = client.value !== "TypedMonarchMoney";
    list.replaceChildren();
    for (const name of groups) {
      const members = selected.filter(method => method.group === name);
      if (!members.length) continue;
      const section = el("section", undefined, "method-group");
      const heading = el("h2", name);
      heading.append(el("span", ` ${members.length}`));
      section.append(heading);
      members.sort((a, b) => (a.name === "get_accounts" ? -1 : b.name === "get_accounts" ? 1 : a.name.localeCompare(b.name)));
      for (const method of members) section.append(cardFor(method));
      list.append(section);
    }
    if (!selected.length) list.append(el("p", "No methods match. Try another name or clear the filters.", "empty"));
  }

  function followHash() {
    let decoded;
    try { decoded = decodeURIComponent(location.hash.slice(1)); } catch (_) { return; }
    const [id, tab] = decoded.split("/");
    const method = methods.find(item => item.id === id);
    if (!method) return;
    client.value = method.client;
    group.value = "";
    search.value = "";
    render();
    const card = document.getElementById(id);
    const selected = panels.find(name => name.toLowerCase() === tab) || "Response";
    openPanel(card, method, selected, false);
    card.open = true;
    requestAnimationFrame(() => card.scrollIntoView({ block: "start" }));
  }

  fetch(app.dataset.catalog)
    .then(response => { if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); })
    .then(catalog => {
      methods = catalog.methods;
      for (const method of methods) {
        method.searchText = [method.name, method.summary, method.group, ...(method.response_fields || []), ...method.parameters.map(parameter => parameter.name), JSON.stringify(method.response_schema || {})].join(" ").toLowerCase();
        if (!groups.includes(method.group)) groups.push(method.group);
      }
      for (const name of groups) {
        const option = el("option", name);
        option.value = name;
        group.append(option);
      }
      search.addEventListener("input", render);
      client.addEventListener("change", render);
      group.addEventListener("change", render);
      document.getElementById("collapse-all").addEventListener("click", () => {
        for (const card of list.querySelectorAll("details.method")) card.open = false;
        history.replaceState(null, "", location.pathname + location.search);
      });
      window.addEventListener("hashchange", followHash);
      render();
      followHash();
    })
    .catch(() => {
      count.textContent = "Could not load the method catalog.";
      list.append(el("p", "Reload this page, or use the Python reference linked above.", "empty"));
    });
})();
