(function () {
  "use strict";

  const app = document.getElementById("drillApp");
  const dataNode = document.getElementById("drillSessionData");
  if (!app || !dataNode) return;

  let phrases = [];
  try {
    phrases = JSON.parse(dataNode.textContent || "[]");
  } catch (_error) {
    return;
  }
  if (!phrases.length) return;

  const mode = app.dataset.mode || "quick";
  const rateUrl = app.dataset.rateUrl;
  const categoryLabels = {
    meeting: "会议沟通",
    audit: "供应商审核",
    factory: "工厂与工艺",
    quality: "质量问题",
    eight_d: "8D 改善",
    interpreting: "陪同与口译",
    claim: "扣款与索赔",
    urgent: "紧急处置",
  };
  const difficultyLabels = {
    foundation: "基础",
    intermediate: "进阶",
    advanced: "高级",
  };

  const elements = {
    category: document.getElementById("cardCategory"),
    difficulty: document.getElementById("cardDifficulty"),
    counter: document.getElementById("cardCounter"),
    progress: document.getElementById("sessionProgress"),
    contextWrap: document.getElementById("cardContextWrap"),
    context: document.getElementById("cardContext"),
    chineseWrap: document.getElementById("cardChineseWrap"),
    chinese: document.getElementById("cardChinese"),
    listeningPrompt: document.getElementById("listeningPrompt"),
    playPrompt: document.getElementById("playPrompt"),
    assemblyArea: document.getElementById("assemblyArea"),
    assemblyAnswer: document.getElementById("assemblyAnswer"),
    assemblyPlaceholder: document.getElementById("assemblyPlaceholder"),
    assemblyTokens: document.getElementById("assemblyTokens"),
    assemblyFeedback: document.getElementById("assemblyFeedback"),
    answerArea: document.getElementById("answerArea"),
    english: document.getElementById("cardEnglish"),
    alternativesWrap: document.getElementById("alternativesWrap"),
    alternatives: document.getElementById("cardAlternatives"),
    note: document.getElementById("cardNote"),
    primaryActions: document.getElementById("primaryActions"),
    reveal: document.getElementById("revealButton"),
    ratingActions: document.getElementById("ratingActions"),
    silentHint: document.getElementById("silentHint"),
    completed: document.getElementById("sessionCompleted"),
    again: document.getElementById("againCount"),
    good: document.getElementById("goodCount"),
    easy: document.getElementById("easyCount"),
    audioToggle: document.getElementById("audioToggle"),
    audioLabel: document.getElementById("audioLabel"),
    audioIconOff: document.getElementById("audioIconOff"),
    audioIconOn: document.getElementById("audioIconOn"),
    categorySelect: document.getElementById("drillCategory"),
    practiceSurface: document.getElementById("practiceSurface"),
  };

  let currentIndex = 0;
  let selectedChunks = [];
  let shuffledChunks = [];
  let revealed = false;
  let lastAssemblyCorrect = null;
  const scores = { again: 0, good: 0, easy: 0 };
  let audioEnabled = window.localStorage.getItem("sqeEnglishAudio") === "on";

  function currentPhrase() {
    return phrases[currentIndex];
  }

  function escapeText(value) {
    return String(value == null ? "" : value);
  }

  function fallbackChunks(sentence) {
    const words = escapeText(sentence).trim().split(/\s+/).filter(Boolean);
    const size = words.length <= 16 ? 4 : 5;
    const result = [];
    for (let index = 0; index < words.length; index += size) {
      result.push(words.slice(index, index + size).join(" "));
    }
    return result;
  }

  function shuffled(values) {
    const result = values.map(function (text, index) {
      return { text: text, originalIndex: index };
    });
    for (let index = result.length - 1; index > 0; index -= 1) {
      const target = Math.floor(Math.random() * (index + 1));
      const temp = result[index];
      result[index] = result[target];
      result[target] = temp;
    }
    if (result.length > 1 && result.every(function (item, index) {
      return item.originalIndex === index;
    })) {
      result.reverse();
    }
    return result;
  }

  function updateAudioButton() {
    elements.audioToggle.setAttribute("aria-pressed", audioEnabled ? "true" : "false");
    elements.audioLabel.textContent = audioEnabled ? "耳机朗读" : "办公室静音";
    elements.audioIconOff.classList.toggle("hidden", audioEnabled);
    elements.audioIconOn.classList.toggle("hidden", !audioEnabled);
    elements.audioToggle.classList.toggle("border-blue-300", audioEnabled);
    elements.audioToggle.classList.toggle("bg-blue-50", audioEnabled);
    elements.audioToggle.classList.toggle("text-blue-700", audioEnabled);
  }

  function speakCurrent() {
    if (!("speechSynthesis" in window)) {
      elements.silentHint.textContent = "当前浏览器不支持语音朗读";
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(currentPhrase().en);
    utterance.lang = "en-US";
    utterance.rate = 0.88;
    utterance.pitch = 1;
    const voices = window.speechSynthesis.getVoices();
    const preferred = voices.find(function (voice) {
      return /^en-(US|GB)/i.test(voice.lang);
    });
    if (preferred) utterance.voice = preferred;
    window.speechSynthesis.speak(utterance);
  }

  function resetAnswer() {
    revealed = false;
    lastAssemblyCorrect = null;
    elements.answerArea.classList.add("hidden");
    elements.ratingActions.classList.add("hidden");
    elements.primaryActions.classList.remove("hidden");
    elements.alternativesWrap.classList.add("hidden");
    elements.note.classList.add("hidden");
    elements.assemblyFeedback.className = "mt-3 hidden text-sm font-semibold";
    elements.assemblyFeedback.textContent = "";
  }

  function renderAssemblyAnswer() {
    elements.assemblyAnswer.querySelectorAll("[data-selected-position]").forEach(function (node) {
      node.remove();
    });
    elements.assemblyPlaceholder.classList.toggle("hidden", selectedChunks.length > 0);
    selectedChunks.forEach(function (item, position) {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.selectedPosition = String(position);
      button.className = "mr-2 mb-2 rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-800 hover:bg-blue-100";
      button.textContent = item.text;
      button.addEventListener("click", function () {
        const removed = selectedChunks.splice(position, 1)[0];
        shuffledChunks.find(function (chunk) {
          return chunk.originalIndex === removed.originalIndex;
        }).used = false;
        renderAssembly();
      });
      elements.assemblyAnswer.appendChild(button);
    });
  }

  function renderAssembly() {
    renderAssemblyAnswer();
    elements.assemblyTokens.innerHTML = "";
    shuffledChunks.forEach(function (item) {
      if (item.used) return;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-semibold text-gray-700 hover:border-blue-400 hover:text-blue-700";
      button.textContent = item.text;
      button.addEventListener("click", function () {
        item.used = true;
        selectedChunks.push(item);
        renderAssembly();
      });
      elements.assemblyTokens.appendChild(button);
    });
  }

  function renderCard() {
    const phrase = currentPhrase();
    resetAnswer();
    selectedChunks = [];

    elements.category.textContent = categoryLabels[phrase.cat] || phrase.cat || "工作英语";
    elements.difficulty.textContent = difficultyLabels[phrase.difficulty] || "进阶";
    elements.counter.textContent = String(currentIndex + 1) + " / " + String(phrases.length);
    elements.progress.style.width = String((currentIndex / phrases.length) * 100) + "%";
    elements.context.textContent = phrase.context || "";
    elements.contextWrap.classList.toggle("hidden", !phrase.context);
    elements.chinese.textContent = phrase.cn || "";
    elements.english.textContent = phrase.en || "";
    elements.note.textContent = phrase.note || "";
    elements.note.classList.toggle("hidden", !phrase.note);
    elements.alternatives.innerHTML = "";
    (phrase.alternatives || []).forEach(function (alternative) {
      const line = document.createElement("p");
      line.textContent = alternative;
      elements.alternatives.appendChild(line);
    });

    elements.listeningPrompt.classList.toggle("hidden", mode !== "listening");
    elements.chineseWrap.classList.toggle("hidden", mode === "listening");
    elements.assemblyArea.classList.toggle("hidden", mode !== "assembly");

    if (mode === "assembly") {
      const chunks = Array.isArray(phrase.chunks) && phrase.chunks.length > 1
        ? phrase.chunks
        : fallbackChunks(phrase.en);
      shuffledChunks = shuffled(chunks);
      renderAssembly();
      elements.reveal.querySelector("span").textContent = "检查表达";
      elements.silentHint.textContent = "点击词组，按正确顺序组成句子";
    } else if (mode === "listening") {
      elements.reveal.querySelector("span").textContent = "显示内容";
      elements.silentHint.textContent = "点击播放后，在心里复述意思";
      if (audioEnabled) speakCurrent();
    } else {
      elements.reveal.querySelector("span").textContent = "显示参考表达";
      elements.silentHint.textContent = "无需开口，在心里组织完整句子";
    }
  }

  function revealAnswer() {
    if (revealed) return;
    const phrase = currentPhrase();
    revealed = true;

    if (mode === "assembly") {
      const selectedOrder = selectedChunks.map(function (item) {
        return item.originalIndex;
      });
      lastAssemblyCorrect =
        selectedOrder.length === shuffledChunks.length &&
        selectedOrder.every(function (value, index) { return value === index; });
      elements.assemblyFeedback.classList.remove("hidden");
      elements.assemblyFeedback.classList.add(lastAssemblyCorrect ? "text-emerald-700" : "text-amber-700");
      elements.assemblyFeedback.textContent = lastAssemblyCorrect
        ? "顺序正确，这句话可以直接用于工作。"
        : "顺序还可以调整，请对照下面的参考表达。";
    }

    if (mode === "listening") {
      elements.chineseWrap.classList.remove("hidden");
    }
    elements.answerArea.classList.remove("hidden");
    elements.alternativesWrap.classList.toggle(
      "hidden",
      !Array.isArray(phrase.alternatives) || phrase.alternatives.length === 0
    );
    elements.note.classList.toggle("hidden", !phrase.note);
    elements.primaryActions.classList.add("hidden");
    elements.ratingActions.classList.remove("hidden");
    if (audioEnabled && mode !== "listening") speakCurrent();
  }

  function updateScore(rating) {
    scores[rating] += 1;
    elements[rating].textContent = String(scores[rating]);
    elements.completed.textContent = String(scores.again + scores.good + scores.easy);
  }

  function finishSession() {
    elements.progress.style.width = "100%";
    elements.primaryActions.classList.add("hidden");
    elements.ratingActions.classList.add("hidden");
    elements.practiceSurface.innerHTML =
      '<div class="mx-auto max-w-lg text-center">' +
        '<div class="mx-auto flex h-12 w-12 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700">' +
          '<svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">' +
            '<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/>' +
          '</svg>' +
        '</div>' +
        '<h2 class="mt-4 text-xl font-bold text-gray-950">本轮练习完成</h2>' +
        '<p class="mt-2 text-sm leading-6 text-gray-500">系统已经根据你的自评安排下一次复习。</p>' +
        '<button id="restartSession" type="button" class="mt-5 rounded-lg bg-gray-900 px-4 py-2.5 text-sm font-semibold text-white">再练一轮</button>' +
      '</div>';
    document.getElementById("restartSession").addEventListener("click", function () {
      window.location.reload();
    });
  }

  async function submitRating(button) {
    const rating = button.dataset.rating;
    const phrase = currentPhrase();
    document.querySelectorAll(".rating-button").forEach(function (item) {
      item.disabled = true;
      item.classList.add("opacity-60");
    });

    try {
      const response = await fetch(rateUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          phrase_id: phrase.id,
          rating: rating,
          mode: mode,
          correct: mode === "assembly" ? lastAssemblyCorrect : null,
          response: mode === "assembly"
            ? selectedChunks.map(function (item) { return item.text; }).join(" ")
            : "",
        }),
      });
      if (!response.ok) throw new Error("Unable to save progress");
      updateScore(rating);
      currentIndex += 1;
      if (currentIndex >= phrases.length) {
        finishSession();
      } else {
        renderCard();
      }
    } catch (_error) {
      elements.silentHint.textContent = "进度保存失败，请稍后重试";
    } finally {
      document.querySelectorAll(".rating-button").forEach(function (item) {
        item.disabled = false;
        item.classList.remove("opacity-60");
      });
    }
  }

  elements.reveal.addEventListener("click", revealAnswer);
  elements.playPrompt.addEventListener("click", speakCurrent);
  elements.audioToggle.addEventListener("click", function () {
    audioEnabled = !audioEnabled;
    window.localStorage.setItem("sqeEnglishAudio", audioEnabled ? "on" : "off");
    updateAudioButton();
    if (audioEnabled && mode === "listening") speakCurrent();
    if (!audioEnabled && "speechSynthesis" in window) window.speechSynthesis.cancel();
  });
  elements.categorySelect.addEventListener("change", function () {
    const url = new URL(window.location.href);
    if (this.value) {
      url.searchParams.set("category", this.value);
    } else {
      url.searchParams.delete("category");
    }
    url.searchParams.set("mode", mode);
    window.location.href = url.toString();
  });
  document.querySelectorAll(".rating-button").forEach(function (button) {
    button.addEventListener("click", function () {
      submitRating(button);
    });
  });

  updateAudioButton();
  renderCard();
})();
