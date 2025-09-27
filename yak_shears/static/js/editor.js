const maxRetries = 50; // 5 seconds at 100ms intervals
let retries = 0;

function initEditor() {
	const editor = document.querySelector(".editor");
	if (editor) {
		const jar = CodeJar(editor, highlight, {
			addClosing: false,
			spellcheck: true,
			tab: " ".repeat(4),
		});

		// Use the filename from the URL for the key
		const filename = new URLSearchParams(window.location.search).get("file");
		if (filename === null) throw new Error("URL does not have file parameter.");
		const storageKey = `editor_${filename}`;
		const serverContent = window.serverContent;
		editor.textContent = serverContent;
		highlight(editor); // Otherwise only run on key presses

		const saved = localStorage.getItem(storageKey);
		if (saved && saved !== serverContent) {
			// TODO: Make this part of the jinja template instead of added dynamically!
			const toggleDiv = document.createElement("div");
			toggleDiv.className = "editor__toggle";
			toggleDiv.innerHTML = `
       <button id="server-btn" class="active">Server Version</button>
       <button id="local-btn">Unsaved Local Changes</button>
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

		const form = document.getElementById("editor_form");
		if (!form) throw new Error("Could not locate editor_form");
		form.addEventListener("submit", () => {
			// Clear local storage on submit, assuming success
			localStorage.removeItem(storageKey);
		});

		jar.onUpdate((code) => {
			if (code === serverContent) {
				localStorage.removeItem(storageKey);
			} else {
				localStorage.setItem(storageKey, code);
			}
			// PLANNED: Consider how to otherwise prune old unused local storage? Might need a separate local review page which compares against server?
		});
	} else if (retries < maxRetries) {
		retries++;
		setTimeout(initEditor, 100);
	}
}

initEditor();
