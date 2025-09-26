const editor = document.querySelector(".editor");
if (editor) {
	const jar = CodeJar(editor, highlight, {
		tab: " ".repeat(4),
		addClosing: false,
	});

	const storageKey = "index";
	const serverContent = window.serverContent;
	editor.textContent = serverContent;

	const saved = localStorage.getItem(storageKey);
	if (saved && saved !== serverContent) {
		// Add toggle UI for differences
		const toggleDiv = document.createElement("div");
		toggleDiv.className = "editor__toggle";
		toggleDiv.innerHTML = `
      <button id="server-btn" class="active">Server Version</button>
      <button id="local-btn">Local Draft</button>
    `;
		document.querySelector(".editor__header").appendChild(toggleDiv);

		document.getElementById("server-btn").addEventListener("click", () => {
			editor.textContent = serverContent;
			jar.updateCode(serverContent);
			document.getElementById("server-btn").classList.add("active");
			document.getElementById("local-btn").classList.remove("active");
		});

		document.getElementById("local-btn").addEventListener("click", () => {
			editor.textContent = saved;
			jar.updateCode(saved);
			document.getElementById("local-btn").classList.add("active");
			document.getElementById("server-btn").classList.remove("active");
		});
	}

	jar.onUpdate((code) => localStorage.setItem(storageKey, code));
}
