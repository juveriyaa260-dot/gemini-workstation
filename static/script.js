// --- DOM GLOBAL MAPS ---
const input = document.getElementById("prompt");
const sendBtn = document.getElementById("send-btn"); 
const messages = document.getElementById("messages");
const welcomeSection = document.querySelector(".welcome");
const contentPane = document.getElementById("content-pane");
const chipsContainer = document.querySelector(".chips-container");
const historyBox = document.getElementById("sidebar-history-box");
const recentsToggle = document.getElementById("recents-toggle");
const searchInput = document.getElementById("sidebar-search");

const addIcon = document.querySelector(".add-icon");
const hiddenFileInput = document.getElementById("hidden-file-input");
const dropzoneOverlay = document.getElementById("dropzone-overlay");

const settingsBtn = document.querySelector(".profile-settings-btn");
const settingsModal = document.getElementById("settings-modal");
const closeModalBtn = document.getElementById("close-modal-btn");
const clearCacheBtn = document.getElementById("clear-cache-btn");
const exportHistoryBtn = document.getElementById("export-history-btn");

// --- SIDEBAR TOGGLE MECHANISM CONTROLLERS ---
const closeSidebarBtn = document.getElementById("close-sidebar-btn");
const openSidebarBtn = document.getElementById("open-sidebar-btn");
const sidebar = document.querySelector(".sidebar");

// Custom Profile & Preferences DOM Elements
const userNicknameInput = document.getElementById("user-nickname");
const userOccupationInput = document.getElementById("user-occupation");
const userAboutInput = document.getElementById("user-about");
const customInstructionsInput = document.getElementById("custom-instructions");

// Artifact Panel Engine Interfaces
const artifactDrawer = document.getElementById("artifact-drawer");
const closeArtifactBtn = document.getElementById("close-artifact-btn");
const artifactIframe = document.getElementById("artifact-sandbox-iframe");
const artifactTitleText = document.getElementById("artifact-title-text");

// UPGRADE BUTTON MAPS
const manualCanvasBtn = document.getElementById("manual-canvas-btn");
const toggleMonospaceBtn = document.getElementById("toggle-monospace-btn");
const themeProfileSelector = document.getElementById("theme-profile-selector");

let chatHistory = JSON.parse(localStorage.getItem("chatHistory")) || [];
let activeChatId = null; 

// SEPARATED PARSED BUFFERS FOR SYSTEM STAGING
let stagedFilesList = [];  // { name: string, text: string }
let stagedImagesList = []; // { name: string, type: string, base64: string }

let generationIsActive = false;

marked.setOptions({ breaks: true, gfm: true });
const renderer = new marked.Renderer();

// PRODUCTION CODE INTERFACE PARSER
renderer.code = function(codePayload, infostring) {
    let actualCode = "";
    let lang = "text";

    if (codePayload && typeof codePayload === "object") {
        actualCode = codePayload.text || "";
        lang = codePayload.lang || infostring || "text";
    } else {
        actualCode = codePayload || "";
        lang = infostring || "text";
    }

    lang = lang.toLowerCase().replace(/[^a-z0-9]/g, "").trim();

    let safeCode = "";
    try {
        safeCode = btoa(unescape(encodeURIComponent(actualCode)));
    } catch (e) {
        console.error("Base64 Staging Generation Error:", e);
    }

    const previewable = ["html", "htm", "css", "svg", "xml"].includes(lang);

    return `
<div class="code-container">
    <div class="code-header">
        <span>${lang.toUpperCase()}</span>
        <div style="display:flex; gap:10px; align-items:center;">
            ${
                previewable
                ? `
                <span
                class="material-symbols-outlined open-artifact-btn"
                style="cursor: pointer; color: var(--accent-color);"
                onclick="window.triggerArtifactRuntimeRender('${safeCode}','${lang}')">
                open_in_new
                </span>
                `
                : ""
            }
            <span
            class="material-symbols-outlined copy-code-btn"
            style="cursor: pointer;"
            onclick="window.executeSystemClipboardCopy(this,'${safeCode}')">
            content_copy
            </span>
        </div>
    </div>
<pre><code class="language-${lang}">${actualCode.replace(/</g,"&lt;").replace(/>/g,"&gt;")}</code></pre>
</div>
`;
};

marked.use({ renderer });
initializeConsoleAccentTheme();
initializeThemeProfileEngine();

// --- BIND SIDEBAR TOGGLE EVENTS ---
if (closeSidebarBtn && sidebar) {
    closeSidebarBtn.addEventListener("click", () => {
        sidebar.classList.add("collapsed");
    });
}

if (openSidebarBtn && sidebar) {
    openSidebarBtn.addEventListener("click", () => {
        sidebar.classList.remove("collapsed");
    });
}

// --- FEATURE 1: MANUAL SEND TO CANVAS CONTROLLER ---
manualCanvasBtn.addEventListener("click", () => {
    const textContent = input.value.trim();
    if (!textContent) {
        alert("Please paste your HTML, CSS, or SVG code into the chat area input field first!");
        return;
    }

    let targetSource = textContent;
    let inferredLang = "html";

    if (textContent.startsWith("```")) {
        const structuralLines = textContent.split("\n");
        const headerInfo = structuralLines[0].toLowerCase().replace("```", "").trim();
        if (headerInfo) inferredLang = headerInfo;
        
        structuralLines.shift(); 
        if (structuralLines[structuralLines.length - 1].trim() === "```") {
            structuralLines.pop(); 
        }
        targetSource = structuralLines.join("\n");
    } else if (textContent.includes("<html") || textContent.includes("<!DOCTYPE") || textContent.includes("<div")) {
        inferredLang = "html";
    } else if (textContent.includes("{") && textContent.includes(":")) {
        inferredLang = "css";
    }

    try {
        const generatedSafeToken = btoa(unescape(encodeURIComponent(targetSource)));
        window.triggerArtifactRuntimeRender(generatedSafeToken, inferredLang);
    } catch (err) {
        console.error("Manual Staging Sandbox Render Error:", err);
    }
});

// --- FEATURE 2: LIVE THEME SELECTOR HANDLER ---
function initializeThemeProfileEngine() {
    const currentlySavedTheme = localStorage.getItem("workstationThemeProfile") || "cyber-neon";
    themeProfileSelector.value = currentlySavedTheme;
    applyThemeProfileStyles(currentlySavedTheme);

    themeProfileSelector.addEventListener("change", (e) => {
        const targetTheme = e.target.value;
        localStorage.setItem("workstationThemeProfile", targetTheme);
        applyThemeProfileStyles(targetTheme);
    });
}

function applyThemeProfileStyles(theme) {
    const rootElement = document.documentElement;
    if (theme === "frosted-arctic") {
        rootElement.style.setProperty('--glass-bg', 'rgba(255, 255, 255, 0.08)');
        rootElement.style.setProperty('--glass-bg-hover', 'rgba(255, 255, 255, 0.15)');
        rootElement.style.setProperty('--glass-border', 'rgba(255, 255, 255, 0.25)');
        rootElement.style.setProperty('--glass-blur', 'blur(24px)');
        rootElement.style.setProperty('--glass-shadow', '0 8px 32px 0 rgba(255, 255, 255, 0.03)');
        document.body.style.background = "#141619";
    } else if (theme === "obsidian-minimalist") {
        rootElement.style.setProperty('--glass-bg', 'rgba(10, 10, 10, 0.2)');
        rootElement.style.setProperty('--glass-bg-hover', 'rgba(20, 20, 20, 0.4)');
        rootElement.style.setProperty('--glass-border', 'rgba(255, 255, 255, 0.03)');
        rootElement.style.setProperty('--glass-blur', 'blur(8px)');
        rootElement.style.setProperty('--glass-shadow', 'none');
        document.body.style.background = "#020202";
    } else {
        rootElement.style.setProperty('--glass-bg', 'rgba(255, 255, 255, 0.03)');
        rootElement.style.setProperty('--glass-bg-hover', 'rgba(255, 255, 255, 0.07)');
        rootElement.style.setProperty('--glass-border', 'rgba(255, 255, 255, 0.08)');
        rootElement.style.setProperty('--glass-blur', 'blur(16px)');
        rootElement.style.setProperty('--glass-shadow', '0 8px 32px 0 rgba(0, 0, 0, 0.37)');
        document.body.style.background = "#060606";
    }
}

// --- FEATURE 3: MONOSPACE INPUT STYLE TOGGLER ---
toggleMonospaceBtn.addEventListener("click", () => {
    input.classList.toggle("monospace-editor-active");
    if (input.classList.contains("monospace-editor-active")) {
        toggleMonospaceBtn.style.color = "var(--accent-color)";
        input.setAttribute("placeholder", "Entering Monospace Editor Mode. Write clean scripts or paste parameters safely...");
    } else {
        toggleMonospaceBtn.style.color = "";
        input.setAttribute("placeholder", "Ask anything or paste code to preview...");
    }
    input.focus();
});

window.executeSystemClipboardCopy = function(element, base64Code) {
    const code = decodeURIComponent(escape(atob(base64Code)));
    navigator.clipboard.writeText(code).then(() => {
        element.textContent = "check";
        element.classList.add("copy-success-state");
        setTimeout(() => {
            element.textContent = "content_copy";
            element.classList.remove("copy-success-state");
        }, 1500);
    });
};

window.triggerArtifactRuntimeRender = function (base64Code, lang) {
    const code = decodeURIComponent(escape(atob(base64Code)));

    artifactDrawer.classList.add("open-active");
    artifactTitleText.textContent = `Live Canvas Preview (${lang.toUpperCase()})`;

    const iframeDoc = artifactIframe.contentDocument || artifactIframe.contentWindow.document;
    iframeDoc.open();

    if (lang === "html" || lang === "htm") {
        const isFullDocument = /<\s*(!doctype|html|head)\b/i.test(code);
        if (isFullDocument) {
            iframeDoc.write(code);
        } else {
            iframeDoc.write(`
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body>
${code}
</body>
</html>
            `);
        }
    } else if (lang === "css") {
        iframeDoc.write(`
<!DOCTYPE html>
<html>
<head>
<style>
${code}
</style>
</head>
<body>
<div class="demo" style="padding:20px; font-family:sans-serif; color:#ccc;">
    CSS Preview Active. Inside Sandbox environment window rules apply.
</div>
</body>
</html>
        `);
    } else {
        iframeDoc.write(`
<pre style="padding:20px; font-family:monospace; white-space:pre-wrap; color: #333;">
${code}
</pre>
        `);
    }
    iframeDoc.close();
};

closeArtifactBtn.addEventListener("click", () => {
    artifactDrawer.classList.remove("open-active");
});

const attachmentsTray = document.createElement("div");
attachmentsTray.className = "attached-files-tray";
input.parentElement.parentElement.insertBefore(attachmentsTray, input.parentElement);

renderSidebarHistory();

input.addEventListener("input", function() {
    this.style.height = "auto";
    this.style.height = this.scrollHeight + "px";
    updateButtonVisualState();
});

function updateButtonVisualState() {
    if (generationIsActive) {
        sendBtn.textContent = "stop_circle";
        sendBtn.classList.add("stop-active-state");
    } else if (input.value.trim().length > 0 || stagedFilesList.length > 0 || stagedImagesList.length > 0) {
        sendBtn.textContent = "arrow_upward";
        sendBtn.classList.remove("stop-active-state");
    } else {
        sendBtn.textContent = "graphic_eq";
        sendBtn.classList.remove("stop-active-state");
    }
}

input.addEventListener("keydown", function(e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleFormSubmissionTrigger(); }
});

sendBtn.addEventListener("click", handleFormSubmissionTrigger);

function handleFormSubmissionTrigger() {
    if (generationIsActive) {
        generationIsActive = false; updateButtonVisualState();
        const activeCard = document.querySelector(".image-loading-card-wrapper");
        const activeSkeleton = document.querySelector(".skeleton-msg");
        if (activeCard) activeCard.remove();
        if (activeSkeleton) activeSkeleton.remove();
    } else {
        sendMessage();
    }
}

window.addEventListener("keydown", (e) => {
    if (e.ctrlKey && e.key.toLowerCase() === 'n') { e.preventDefault(); startNewChat(); }
    if (e.ctrlKey && e.key.toLowerCase() === 's') { e.preventDefault(); openSettingsModalDashboard(); }
    if (e.key === "Escape") { settingsModal.style.display = "none"; }
});

function openSettingsModalDashboard() {
    settingsModal.style.display = "flex";
    updateGatewayQuotaMeters();

    userNicknameInput.value = localStorage.getItem("userNickname") || "";
    userOccupationInput.value = localStorage.getItem("userOccupation") || "";
    userAboutInput.value = localStorage.getItem("userAbout") || "";
    customInstructionsInput.value = localStorage.getItem("customInstructions") || "";
}

[userNicknameInput, userOccupationInput, userAboutInput, customInstructionsInput].forEach(element => {
    element.addEventListener("input", () => {
        localStorage.setItem("userNickname", userNicknameInput.value.trim());
        localStorage.setItem("userOccupation", userOccupationInput.value.trim());
        localStorage.setItem("userAbout", userAboutInput.value.trim());
        localStorage.setItem("customInstructions", customInstructionsInput.value.trim());
    });
});

recentsToggle.addEventListener("click", () => {
    recentsToggle.classList.toggle("collapsed-trigger");
    historyBox.classList.toggle("hidden-history");
});

document.querySelector(".new-chat").addEventListener("click", startNewChat);

function sendMessage(){
    const text = input.value.trim();
    
    if(!text && stagedFilesList.length === 0 && stagedImagesList.length === 0) return;

    if (!activeChatId) { createNewChatSession(text || stagedImagesList[0]?.name || stagedFilesList[0]?.name); }

    let messageHtmlContent = "";
    let aggregatedFileContext = "";

    if (stagedImagesList.length > 0) {
        stagedImagesList.forEach(img => {
            if (img.type.startsWith("video/")) {
                messageHtmlContent += `
                    <div class="msg-file-pill visual-vid-preview" style="position:relative; max-width:240px; padding:8px;">
                        <span class="material-symbols-outlined" style="color: var(--accent-color);">movie</span>
                        <div style="font-size:12px; color:#fff; text-overflow:ellipsis; overflow:hidden; white-space:nowrap;">${img.name} (Video Attached)</div>
                    </div>`;
            } else {
                messageHtmlContent += `
                    <div class="msg-file-pill visual-img-preview" style="position:relative; max-width:180px; padding:4px; overflow:hidden;">
                        <img src="data:${img.type};base64,${img.base64}" style="width:100%; border-radius:8px; display:block;" />
                        <div style="font-size:10px; color:#aaa; margin-top:4px; text-align:center; text-overflow:ellipsis; overflow:hidden; white-space:nowrap;">${img.name}</div>
                    </div>`;
            }
        });
    }

    if (stagedFilesList.length > 0) {
        stagedFilesList.forEach(file => {
            messageHtmlContent += `<div class="msg-file-pill"><span class="material-symbols-outlined">description</span><span>${file.name}</span></div>`;
            aggregatedFileContext += `--- FILE: ${file.name} ---\n${file.text}\n\n`;
        });
    }
    
    if (text) messageHtmlContent += `<div class="msg-text-body" style="margin-top:6px;">${text}</div>`;

    renderUserBubble(messageHtmlContent);
    saveMessageToActiveChat("user", messageHtmlContent);
    
    const activeChatSession = chatHistory.find(c => c.id === activeChatId);
    const activeHistoryPayload = activeChatSession ? activeChatSession.messages.slice(0, -1) : [];
    const imagesPayloadSnapshot = [...stagedImagesList];

    input.value = ""; input.style.height = "auto";
    generationIsActive = true; updateButtonVisualState();
    
    stagedFilesList = []; stagedImagesList = []; attachmentsTray.innerHTML = ""; 
    messages.scrollTop = messages.scrollHeight;

    const startTimeMark = performance.now();
    
    const skeletonElement = document.createElement("div");
    if (text.toLowerCase().startsWith("/image ")) {
        skeletonElement.className = "image-loading-card-wrapper"; 
        skeletonElement.innerHTML = `
            <div class="image-loading-card">
                <div class="image-loading-title">Creating image</div>
                <div class="image-loading-dots"></div>
            </div>`;
    } else {
        skeletonElement.className = "skeleton-msg";
        skeletonElement.innerHTML = `<div class="skeleton-line" style="width: 85%;"></div><div class="skeleton-line" style="width: 60%;"></div>`;
    }
    
    messages.appendChild(skeletonElement);
    messages.scrollTop = messages.scrollHeight;

    fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
            text: text, 
            history: activeHistoryPayload,
            file_context: aggregatedFileContext,
            images: imagesPayloadSnapshot,
            preferences: {
                nickname: localStorage.getItem("userNickname") || "",
                occupation: localStorage.getItem("userOccupation") || "",
                about: localStorage.getItem("userAbout") || "",
                instructions: localStorage.getItem("customInstructions") || ""
            }
        })
    })
    .then(async res => { 
        const isJson = res.headers.get('content-type')?.includes('application/json');
        const data = isJson ? await res.json() : null;
        
        if (!res.ok) {
            const errText = data?.error || `Server Error Status Code ${res.status}`;
            throw new Error(errText);
        }
        return data;
    })
    .then(data => {
        if (!generationIsActive) return;
        skeletonElement.remove();
        generationIsActive = false; updateButtonVisualState();
        if (data.success) {
            let traceTag = data.was_searched ? ` | 🌐 Grounded` : ``;
            generateAIResponse(data.reply, startTimeMark, traceTag, data.was_searched);
        } else {
            generateAIResponse(`⚠️ Core Processing Error: ${data.error}`, startTimeMark);
        }
    })
    .catch(err => {
        if (!generationIsActive) return;
        skeletonElement.remove();
        generationIsActive = false; updateButtonVisualState();
        generateAIResponse(`❌ System Connectivity Failure: ${err.message}`, startTimeMark);
    });
}

function renderUserBubble(text) {
    const userBubble = document.createElement("div");
    userBubble.className = "user-msg-bubble"; userBubble.innerHTML = text;
    messages.appendChild(userBubble); messages.scrollTop = messages.scrollHeight; 
}

// --- RENDERING ROUTINES ---
function renderSidebarHistory() {
    historyBox.innerHTML = "";
    chatHistory.forEach((chat) => {
        const navItem = document.createElement("div"); navItem.className = "nav-item dynamic-history-item"; navItem.dataset.id = chat.id;
        if (chat.id === activeChatId) navItem.classList.add("active");
        navItem.innerHTML = `
            <span class="material-symbols-outlined">chat_bubble</span>
            <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1;">${chat.title}</span>
            <button class="delete-chat-btn"><span class="material-symbols-outlined">delete</span></button>`;
        navItem.addEventListener("click", (e) => { if (!e.target.closest(".delete-chat-btn")) openChatSession(chat.id); });
        navItem.querySelector(".delete-chat-btn").addEventListener("click", (e) => { e.stopPropagation(); deleteChatSession(chat.id); });
        historyBox.appendChild(navItem);
    });
}

function openChatSession(id) {
    activeChatId = id; const targetChat = chatHistory.find(chat => chat.id === activeChatId);
    if (!targetChat) return;
    welcomeSection.style.display = "none";
    if (document.querySelector(".chips-container")) document.querySelector(".chips-container").style.display = "none";
    messages.style.display = "flex"; contentPane.classList.add("chatting-mode"); messages.innerHTML = "";
    
    targetChat.messages.forEach(msg => {
        const bubble = document.createElement("div");
        if (msg.sender === "user") {
            bubble.className = "user-msg-bubble"; bubble.innerHTML = msg.text;
        } else {
            bubble.className = "ai-msg-container";
            const markdownWrapper = document.createElement("div");
            markdownWrapper.className = "response-markdown-body";
            markdownWrapper.innerHTML = marked.parse(msg.text);
            bubble.appendChild(markdownWrapper); bubble.innerHTML += generateFeedbackActionBar(msg.metrics);
            setTimeout(() => Prism.highlightAllUnder(markdownWrapper), 50);
        }
        messages.appendChild(bubble);
    });
    messages.scrollTop = messages.scrollHeight; renderSidebarHistory(); 
}

function deleteChatSession(id) {
    chatHistory = chatHistory.filter(chat => chat.id !== id); localStorage.setItem("chatHistory", JSON.stringify(chatHistory));
    if (activeChatId === id) startNewChat(); else renderSidebarHistory();
}

function startNewChat() {
    activeChatId = null; messages.innerHTML = ""; messages.style.display = "none";
    input.value = ""; input.style.height = "auto";
    if (welcomeSection) {
        welcomeSection.style.display = "block";
        if (document.querySelector(".chips-container")) document.querySelector(".chips-container").style.display = "flex";
        contentPane.classList.remove("chatting-mode");
    }
    artifactDrawer.classList.remove("open-active"); 
    renderSidebarHistory();
}

addIcon.addEventListener("click", () => { hiddenFileInput.click(); });
hiddenFileInput.addEventListener("change", (e) => { processIncomingFiles(e.target.files); hiddenFileInput.value = ""; });
window.addEventListener("dragenter", (e) => { e.preventDefault(); dropzoneOverlay.style.display = "flex"; });
dropzoneOverlay.addEventListener("dragleave", (e) => {
    e.preventDefault();
    if (e.clientX <= 0 || e.clientY <= 0 || e.clientX >= window.innerWidth || e.clientY >= window.innerHeight) dropzoneOverlay.style.display = "none";
});
window.addEventListener("dragover", (e) => { e.preventDefault(); });
window.addEventListener("drop", (e) => { e.preventDefault(); dropzoneOverlay.style.display = "none"; if (e.dataTransfer.files.length > 0) processIncomingFiles(e.dataTransfer.files); });

function processIncomingFiles(files) {
    for (let file of files) {
        const isImg = file.type.startsWith("image/");
        const isVid = file.type.startsWith("video/");
        const reader = new FileReader();
        
        reader.onload = function(evt) {
            if (isImg || isVid) {
                const base64Data = evt.target.result.split(",")[1];
                const mediaObj = { name: file.name, type: file.type, base64: base64Data };
                if (!stagedImagesList.some(i => i.name === file.name)) {
                    stagedImagesList.push(mediaObj);
                    renderVisualChipInTray(mediaObj, isVid ? null : evt.target.result);
                }
            } else {
                const fileObj = { name: file.name, text: evt.target.result };
                if (!stagedFilesList.some(f => f.name === file.name)) {
                    stagedFilesList.push(fileObj);
                    renderTextChipInTray(fileObj);
                }
            }
        };

        if (isImg || isVid) {
            reader.readAsDataURL(file);
        } else {
            reader.readAsText(file);
        }
    }
}

function renderVisualChipInTray(mediaObj, dataUrl) {
    const chip = document.createElement("div"); 
    chip.className = "file-preview-chip";
    chip.style.borderColor = "var(--accent-color)";
    
    const mediaPreview = dataUrl 
        ? `<img src="${dataUrl}" style="width:20px; height:20px; object-fit:cover; border-radius:4px;" />`
        : `<span class="material-symbols-outlined file-icon" style="color: var(--accent-color); font-size: 18px;">movie</span>`;

    chip.innerHTML = `
        ${mediaPreview}
        <span class="file-name-text">${mediaObj.name}</span>
        <span class="material-symbols-outlined remove-file-btn">close</span>`;
    chip.querySelector(".remove-file-btn").addEventListener("click", () => { 
        stagedImagesList = stagedImagesList.filter(i => i.name !== mediaObj.name); 
        chip.remove(); updateButtonVisualState(); 
    });
    attachmentsTray.appendChild(chip); updateButtonVisualState();
}

function renderTextChipInTray(fileObj) {
    const chip = document.createElement("div"); 
    chip.className = "file-preview-chip";
    chip.innerHTML = `<span class="material-symbols-outlined file-icon">description</span><span class="file-name-text">${fileObj.name}</span><span class="material-symbols-outlined remove-file-btn">close</span>`;
    chip.querySelector(".remove-file-btn").addEventListener("click", () => { 
        stagedFilesList = stagedFilesList.filter(f => f.name !== fileObj.name); 
        chip.remove(); updateButtonVisualState(); 
    });
    attachmentsTray.appendChild(chip); updateButtonVisualState();
}

function generateAIResponse(reply, startTimeMark, trackingSuffix = "", wasSearched = false) {
    const totalLatencySec = ((performance.now() - startTimeMark) / 1000).toFixed(2);
    const wordCount = reply.split(" ").length;
    let metricsString = `Words: ${wordCount} | Latency: ${totalLatencySec}s${trackingSuffix}`;

    saveMessageToActiveChat("ai", reply, metricsString);

    const aiContainer = document.createElement("div");
    aiContainer.className = "ai-msg-container";

    const markdownWrapper = document.createElement("div");
    markdownWrapper.className = "response-markdown-body";

    aiContainer.appendChild(markdownWrapper);
    messages.appendChild(aiContainer);

    function appendSourcesDrawerLayout() {
        const utilityWrapper = document.createElement("div");
        utilityWrapper.innerHTML = generateFeedbackActionBar(metricsString);
        aiContainer.appendChild(utilityWrapper.firstElementChild);
        messages.scrollTop = messages.scrollHeight;
    }

    const containsCode = reply.includes("```") || reply.includes("<!DOCTYPE") || reply.includes("<html") || reply.includes("<head") || reply.includes("<body") || reply.includes("<style") || reply.includes("<script");

    if (containsCode) {
        markdownWrapper.innerHTML = marked.parse(reply);
        Prism.highlightAllUnder(markdownWrapper);
        appendSourcesDrawerLayout();
        return;
    }

    let index = 0;
    const words = reply.split(" ");
    let compiledText = "";

    const streamer = setInterval(() => {
        if (index < words.length) {
            compiledText += (index === 0 ? "" : " ") + words[index];
            markdownWrapper.innerHTML = marked.parse(compiledText);
            index++;
            messages.scrollTop = messages.scrollHeight;
        } else {
            clearInterval(streamer);
            markdownWrapper.innerHTML = marked.parse(reply);
            Prism.highlightAllUnder(markdownWrapper);
            appendSourcesDrawerLayout();
        }
    }, 20);
}

function generateFeedbackActionBar(metrics) {
    return `
        <div class="feedback-container">
            <div class="feedback-actions"><span class="material-symbols-outlined copy-msg-btn" onclick="executeClipboardMessageCopy(this)">content_copy</span><span class="material-symbols-outlined">thumb_up</span><span class="material-symbols-outlined">thumb_down</span></div>
            <div class="metrics-tag">${metrics || ""}</div>
        </div>`;
}

window.executeClipboardMessageCopy = function(element) {
    const parentContainer = element.closest('.ai-msg-container');
    const targetText = parentContainer.querySelector('.response-markdown-body').innerText;
    navigator.clipboard.writeText(targetText).then(() => {
        element.textContent = "check";
        element.style.color = "var(--accent-color)";
        setTimeout(() => {
            element.textContent = "content_copy";
            element.style.color = "";
        }, 1500);
    });
};

saveMessageToActiveChat = function(sender, text, metrics) {
    const currentChat = chatHistory.find(chat => chat.id === activeChatId);
    if (currentChat) {
        currentChat.messages.push({ sender: sender, text: text, metrics: metrics || "" });
        localStorage.setItem("chatHistory", JSON.stringify(chatHistory));
    }
};

searchInput.addEventListener("input", () => {
    const query = searchInput.value.toLowerCase().trim();
    document.querySelectorAll(".dynamic-history-item").forEach(item => {
        item.style.display = item.querySelector("span:not(.material-symbols-outlined)").textContent.toLowerCase().includes(query) ? "flex" : "none";
    });
});

settingsBtn.addEventListener("click", openSettingsModalDashboard);
closeModalBtn.addEventListener("click", () => { settingsModal.style.display = "none"; });

function initializeConsoleAccentTheme() { 
    const savedColor = localStorage.getItem("consoleAccentColor") || "#10b981";
    document.documentElement.style.setProperty('--accent-color', savedColor); 
    
    document.querySelectorAll(".color-dot").forEach(dot => {
        const dotColor = dot.getAttribute("data-color");
        if (dotColor === savedColor) dot.classList.add("selected-dot");
        
        dot.addEventListener("click", () => {
            document.querySelectorAll(".color-dot").forEach(d => d.classList.remove("selected-dot"));
            dot.classList.add("selected-dot");
            localStorage.setItem("consoleAccentColor", dotColor);
            document.documentElement.style.setProperty('--accent-color', dotColor);
        });
    });
}

window.applyQuickImagePrompt = function() {
    const promptInput = document.getElementById("prompt");
    promptInput.value = "/image a futuristic neon metropolis cyber workstation, cinematic lighting, 8k resolution";
    promptInput.style.height = "auto";
    promptInput.style.height = promptInput.scrollHeight + "px";
    promptInput.focus();
    updateButtonVisualState();
};

function updateGatewayQuotaMeters() {
    const container = document.getElementById("quota-bars-container");
    if (!container) return;

    fetch("/quota_status")
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                container.innerHTML = ""; 
                
                for (let i = 1; i <= 5; i++) {
                    const status = data.tracker[i] || { used: 0, max: 1500 };
                    const percent = ((status.used / status.max) * 100).toFixed(0);
                    
                    const barRow = document.createElement("div");
                    barRow.className = "quota-bar-row";
                    barRow.style.cssText = "width: 100%; display: flex; flex-direction: column; gap: 4px;";
                    
                    barRow.innerHTML = `
                        <div style="display: flex; justify-content: space-between; font-size: 12px; color: #b4b4b4; font-family: monospace;">
                            <span>Key Slot #${i}</span>
                            <span>${status.used}/${status.max} (${percent}%)</span>
                        </div>
                        <div class="quota-meter-bg" style="width: 100%; height: 6px; background: #222; border-radius: 3px; overflow: hidden; position: relative;">
                            <div class="quota-meter-fill" style="width: ${percent}%; height: 100%; background: var(--accent-color); transition: width 0.4s ease; border-radius: 3px;"></div>
                        </div>
                    `;
                    container.appendChild(barRow);
                }
            }
        })
        .catch(err => console.error("Error retrieving cluster allocation matrices:", err));
}

window.toggleSourcesDrawerMatrix = function(element) {
    element.classList.toggle("expanded");
    const container = element.closest('.sources-collapse-wrapper');
    const body = container.querySelector('.sources-content-body');
    body.classList.toggle("show");
};

// --- FEATURE 4: GENERAL PRODUCTIVITY WORKFLOW ROUTERS ---
window.triggerWorkflow = function(type) {
    const promptInput = document.getElementById("prompt");
    const existingText = promptInput.value.trim();
    
    let commandInstruction = "";
    if (type === 'explain') {
        commandInstruction = "Break down the core concepts from the workspace files or query above into high-fidelity, easy-to-digest terms. Use clear logical analogies where applicable.";
    } else if (type === 'refactor') {
        commandInstruction = "Review the architecture of the provided system specifications or source snippets. Optimize patterns, reduce overhead, eliminate anomalies, and write beautifully structured code accompanied by explicit markdown inline-comments.";
    } else if (type === 'document') {
        commandInstruction = "Generate comprehensive, production-grade technical documentation detailing the components, APIs, layout elements, and configuration rules from the workspace context files above.";
    }

    if (existingText) {
        promptInput.value = existingText + "\n\n" + commandInstruction;
    } else {
        promptInput.value = commandInstruction;
    }
    
    promptInput.style.height = "auto";
    promptInput.style.height = promptInput.scrollHeight + "px";
    
    handleFormSubmissionTrigger();
};
