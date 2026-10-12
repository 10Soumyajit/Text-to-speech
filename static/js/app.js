/**
 * Text-to-Speech (Sheetal's Voice) - Studio Frontend Logic
 */

document.addEventListener("DOMContentLoaded", () => {
    // DOM Elements
    const inputText = document.getElementById("input-text");
    const charCount = document.getElementById("char-count");
    const wordCount = document.getElementById("word-count");
    const validationHint = document.getElementById("validation-hint");
    const btnClearText = document.getElementById("btn-clear-text");

    const btnGenerate = document.getElementById("btn-generate");
    const btnRegenerate = document.getElementById("btn-regenerate");
    const btnDownload = document.getElementById("btn-download");

    const errorBanner = document.getElementById("error-banner");
    const errorTitle = document.getElementById("error-title");
    const errorMessage = document.getElementById("error-message");
    const btnCloseError = document.getElementById("btn-close-error");

    const creditBanner = document.getElementById("credit-banner");
    const creditMessage = document.getElementById("credit-message");
    const btnCloseCredit = document.getElementById("btn-close-credit");

    const successBanner = document.getElementById("success-banner");
    const successTitle = document.getElementById("success-title");
    const successMessage = document.getElementById("success-message");
    const btnCloseSuccess = document.getElementById("btn-close-success");

    const loadingState = document.getElementById("loading-state");
    const loadingTitle = document.getElementById("loading-title");
    const loadingSub = document.getElementById("loading-sub");

    const playerEmptyState = document.getElementById("player-empty-state");
    const customPlayerWrapper = document.getElementById("custom-player-wrapper");
    const audioPreview = document.getElementById("audio-preview");
    const btnPlayPause = document.getElementById("btn-play-pause");
    const playIcon = btnPlayPause.querySelector(".play-icon");
    const pauseIcon = btnPlayPause.querySelector(".pause-icon");
    const currentTimeEl = document.getElementById("current-time");
    const totalTimeEl = document.getElementById("total-time");
    const seekBar = document.getElementById("seek-bar");
    const seekFill = document.getElementById("seek-fill");
    const btnVolume = document.getElementById("btn-volume");
    const volumeSlider = document.getElementById("volume-slider");
    const durationBadge = document.getElementById("audio-duration-badge");
    const metaMode = document.getElementById("meta-mode");
    const metaStatus = document.getElementById("meta-status");

    const voiceIdBadge = document.getElementById("voice-id-badge");

    // State Variables
    let currentAudioId = null;
    let isGenerating = false;
    let lastVolume = 1.0;

    // 1. Text Area Input & Counters
    function updateCounters() {
        const text = inputText.value;
        const length = text.length;
        charCount.textContent = length;

        const words = text.trim() ? text.trim().split(/\s+/).length : 0;
        wordCount.textContent = words;

        if (length === 0) {
            validationHint.textContent = "Ready for synthesis";
            validationHint.style.color = "var(--text-dim)";
        } else if (length > 3000) {
            validationHint.textContent = "Exceeds 3000 character limit";
            validationHint.style.color = "var(--accent-rose)";
        } else {
            validationHint.textContent = `${words} word${words !== 1 ? 's' : ''} ready`;
            validationHint.style.color = "var(--accent-emerald)";
        }
    }

    inputText.addEventListener("input", () => {
        updateCounters();
        hideError();
    });

    btnClearText.addEventListener("click", () => {
        inputText.value = "";
        updateCounters();
        inputText.focus();
        hideError();
    });

    // 2. Sample Chips
    document.querySelectorAll(".chip").forEach(chip => {
        chip.addEventListener("click", () => {
            const sampleText = chip.getAttribute("data-sample");
            if (sampleText) {
                inputText.value = sampleText;
                updateCounters();
                inputText.focus();
                hideError();
            }
        });
    });

    // 3. Alert Helpers
    function showError(title, msg) {
        creditBanner.classList.add("hidden");
        errorTitle.textContent = title || "Validation Error";
        errorMessage.textContent = msg;
        errorBanner.classList.remove("hidden");
        errorBanner.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    function hideError() {
        errorBanner.classList.add("hidden");
    }

    function showCreditExhaustion(msg) {
        errorBanner.classList.add("hidden");
        if (msg) {
            creditMessage.textContent = msg;
        }
        creditBanner.classList.remove("hidden");
        creditBanner.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    function hideCreditExhaustion() {
        creditBanner.classList.add("hidden");
    }

    function showSuccess(title, msg) {
        successTitle.textContent = title || "Success";
        successMessage.textContent = msg;
        successBanner.classList.remove("hidden");
        setTimeout(() => {
            successBanner.classList.add("hidden");
        }, 5000);
    }

    btnCloseError.addEventListener("click", hideError);
    btnCloseCredit.addEventListener("click", hideCreditExhaustion);
    btnCloseSuccess.addEventListener("click", () => successBanner.classList.add("hidden"));

    // 4. Input Validation
    function validateInput() {
        const text = inputText.value;

        if (!text || text.length === 0) {
            showError("Missing Input Text", "Please enter some text in the textfield before generating speech.");
            inputText.focus();
            return false;
        }

        const trimmed = text.trim();
        if (trimmed.length === 0) {
            showError("Invalid Content", "Text cannot contain only spaces or whitespace. Please provide readable content.");
            inputText.focus();
            return false;
        }

        if (trimmed.length > 3000) {
            showError("Character Limit Exceeded", `Your input has ${trimmed.length} characters, which exceeds the HeyGen Starfish limit of 3000 characters.`);
            inputText.focus();
            return false;
        }

        return trimmed;
    }

    // 5. Synthesis Execution (Standard & Force-New Regenerate)
    async function executeSynthesis(forceNew = false) {
        if (isGenerating) return;

        hideError();
        hideCreditExhaustion();

        const validText = validateInput();
        if (!validText) return;

        // Set Loading UI
        isGenerating = true;
        btnGenerate.disabled = true;
        btnRegenerate.disabled = true;
        btnDownload.disabled = true;

        loadingTitle.textContent = forceNew
            ? "Regenerating Sheetal's voice (--force-new)..."
            : "Synthesizing Sheetal's voice...";
        loadingSub.textContent = forceNew
            ? "Bypassing HeyGen server cache with unique SSML nonce & micro-pause"
            : "Sending request to HeyGen Starfish neural engine";
        loadingState.classList.remove("hidden");

        try {
            const response = await fetch("/api/generate", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    text: validText,
                    force_new: forceNew
                })
            });

            const data = await response.json();

            if (!response.ok || !data.success) {
                // Check if error is due to credit exhaustion
                if (data.error_type === "CREDITS_EXHAUSTED" || response.status === 402) {
                    showCreditExhaustion(data.error);
                } else if (data.error_type?.startsWith("VALIDATION_")) {
                    showError("Input Validation Error", data.error);
                } else if (data.error_type === "AUTH_ERROR" || data.error_type === "CONFIG_ERROR") {
                    showError("Configuration / Authentication Error", data.error);
                } else {
                    showError("Speech Generation Failed", data.error || "An unknown error occurred while processing audio.");
                }
                return;
            }

            // Success Handling
            currentAudioId = data.audio_id;

            // Load audio preview without saving/downloading to disk
            // Force reset audio player and bust any browser audio element cache
            audioPreview.pause();
            audioPreview.currentTime = 0;
            audioPreview.src = `${data.preview_url}?_t=${Date.now()}`;
            audioPreview.load();

            // Reveal player
            playerEmptyState.classList.add("hidden");
            customPlayerWrapper.classList.remove("hidden");

            // Enable download button
            btnDownload.disabled = false;
            btnDownload.title = "Download synthesized audio (.wav)";

            // Update badges and meta
            if (data.duration) {
                durationBadge.textContent = `${data.duration}s`;
                durationBadge.classList.remove("hidden");
            }
            metaMode.textContent = forceNew ? "Mode: Regenerated (--force-new)" : "Mode: Standard";
            metaStatus.textContent = forceNew ? "Status: Fresh regeneration ready" : "Status: Ready for preview";

            showSuccess(
                forceNew ? "Regeneration Complete (--force-new)" : "Speech Generated",
                data.message || (forceNew ? "Speech regenerated fresh bypassing cache with --force-new!" : "Audio is now ready for in-browser preview.")
            );

            // Auto-play preview
            audioPreview.play().then(() => {
                setPlayState(true);
            }).catch(() => {
                // Browser autoplay policy might require manual click
                setPlayState(false);
            });

        } catch (err) {
            showError("Network Error", `Could not connect to the server: ${err.message}. Please check your server status.`);
        } finally {
            isGenerating = false;
            btnGenerate.disabled = false;
            btnRegenerate.disabled = false;
            loadingState.classList.add("hidden");
        }
    }

    // 6. Action Button Listeners
    btnGenerate.addEventListener("click", () => executeSynthesis(false));
    btnRegenerate.addEventListener("click", () => executeSynthesis(true));

    // 7. Download Action
    btnDownload.addEventListener("click", () => {
        if (!currentAudioId) {
            showError("No Audio", "Please generate an audio clip first before downloading.");
            return;
        }

        // Trigger explicit download
        const downloadUrl = `/api/download/${currentAudioId}`;
        const tempLink = document.createElement("a");
        tempLink.href = downloadUrl;
        tempLink.setAttribute("download", `sheetal_speech_${currentAudioId.substring(0, 8)}.wav`);
        document.body.appendChild(tempLink);
        tempLink.click();
        document.body.removeChild(tempLink);

        showSuccess("Download Started", "Your audio file is downloading.");
    });

    // 8. Custom Audio Player Controls
    function formatTime(seconds) {
        if (isNaN(seconds) || seconds < 0) return "0:00";
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
    }

    function setPlayState(isPlaying) {
        if (isPlaying) {
            playIcon.classList.add("hidden");
            pauseIcon.classList.remove("hidden");
            metaStatus.textContent = "Status: Playing preview...";
        } else {
            playIcon.classList.remove("hidden");
            pauseIcon.classList.add("hidden");
            metaStatus.textContent = "Status: Paused";
        }
    }

    btnPlayPause.addEventListener("click", () => {
        if (!audioPreview.src) return;

        if (audioPreview.paused) {
            audioPreview.play();
            setPlayState(true);
        } else {
            audioPreview.pause();
            setPlayState(false);
        }
    });

    audioPreview.addEventListener("timeupdate", () => {
        const current = audioPreview.currentTime;
        const total = audioPreview.duration;

        currentTimeEl.textContent = formatTime(current);

        if (!isNaN(total) && total > 0) {
            const progress = (current / total) * 100;
            seekBar.value = progress;
            seekFill.style.width = `${progress}%`;
        }
    });

    audioPreview.addEventListener("loadedmetadata", () => {
        const total = audioPreview.duration;
        totalTimeEl.textContent = formatTime(total);
        seekBar.value = 0;
        seekFill.style.width = "0%";
    });

    audioPreview.addEventListener("ended", () => {
        setPlayState(false);
        seekBar.value = 0;
        seekFill.style.width = "0%";
        currentTimeEl.textContent = "0:00";
        metaStatus.textContent = "Status: Playback finished";
    });

    seekBar.addEventListener("input", () => {
        if (!isNaN(audioPreview.duration)) {
            const targetTime = (seekBar.value / 100) * audioPreview.duration;
            audioPreview.currentTime = targetTime;
            seekFill.style.width = `${seekBar.value}%`;
            currentTimeEl.textContent = formatTime(targetTime);
        }
    });

    volumeSlider.addEventListener("input", (e) => {
        const vol = parseFloat(e.target.value);
        audioPreview.volume = vol;
        if (vol > 0) lastVolume = vol;
    });

    btnVolume.addEventListener("click", () => {
        if (audioPreview.volume > 0) {
            audioPreview.volume = 0;
            volumeSlider.value = 0;
        } else {
            const restored = lastVolume || 1.0;
            audioPreview.volume = restored;
            volumeSlider.value = restored;
        }
    });

    // 9. Copy Voice ID helper
    if (voiceIdBadge) {
        voiceIdBadge.addEventListener("click", () => {
            const voiceIdText = document.getElementById("voice-id-text").textContent.trim();
            navigator.clipboard.writeText(voiceIdText).then(() => {
                showSuccess("Copied", `Voice ID '${voiceIdText}' copied to clipboard.`);
            }).catch(() => {
                // Fallback
            });
        });
    }

    // Initialize character counter on load
    updateCounters();
});
