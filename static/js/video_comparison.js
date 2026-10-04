/* In-image video comparison, adapted from the original project-page code.
 * Original: Lukas Radl (April 2024), based on Ref-NeRF, Reconfusion and DICS.
 * Retains the original left-frame/right-crop compositing and pointer tracking.
 * Each container owns its position and loop; hidden media never keeps drawing.
 */
"use strict";
(() => {
  class VideoComparison {
    constructor(container) {
      this.container = container;
      this.video = container.querySelector("video");
      this.canvas = container.querySelector("canvas");
      this.context = this.canvas.getContext("2d");
      this.button = container.querySelector(".play-comparison");
      this.status = container.querySelector('[role="status"]');
      this.position = 0.5;
      this.raf = null;
      this.inViewport = false;
      this.manuallyPaused = false;
      this.reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
      this.lastTime = -1;
      this.video.controls = false;
      this.canvas.tabIndex = 0;
      this.canvas.setAttribute("role", "slider");
      this.canvas.setAttribute("aria-valuemin", "0");
      this.canvas.setAttribute("aria-valuemax", "100");
      this.button.setAttribute("aria-pressed", "false");
      this.setPosition(0.5);
      this.button.addEventListener("click", () => {
        this.manuallyPaused = !this.video.paused;
        if (this.video.paused) this.play();
        else this.video.pause();
      });
      this.video.addEventListener("loadeddata", () => {
        this.resize();
        // Keep the decoding source in the DOM like the original implementation.
        this.video.classList.add("video-source-loaded");
        this.canvas.hidden = false;
        this.container.classList.remove("is-loading");
        this.draw();
      });
      this.video.addEventListener("play", () => {
        this.button.textContent = "Pause comparison";
        this.button.setAttribute("aria-pressed", "true");
        this.status.textContent = "";
        this.startLoop();
      });
      this.video.addEventListener("playing", () => {
        this.container.classList.remove("is-loading");
        this.startLoop();
      });
      this.video.addEventListener("pause", () => {
        this.stopLoop();
        this.button.textContent = "Play comparison";
        this.button.setAttribute("aria-pressed", "false");
        this.container.classList.remove("is-loading");
      });
      this.video.addEventListener("waiting", () => {
        if (!this.video.paused) this.container.classList.add("is-loading");
      });
      this.video.addEventListener("seeked", () => this.draw());
      this.video.addEventListener("error", () => {
        this.video.pause();
        this.stopLoop();
        this.container.classList.remove("is-loading");
        this.status.textContent = "This comparison could not be loaded. Reload the page to try again.";
      });
      this.canvas.addEventListener("pointermove", event => {
        if (event.pointerType === "mouse" || event.buttons) this.pointer(event);
      });
      this.canvas.addEventListener("pointerdown", event => {
        this.canvas.setPointerCapture(event.pointerId);
        this.pointer(event);
      });
      this.canvas.addEventListener("keydown", event => {
        let value = this.position;
        if (event.key === "ArrowLeft") value -= 0.05;
        else if (event.key === "ArrowRight") value += 0.05;
        else if (event.key === "Home") value = 0;
        else if (event.key === "End") value = 1;
        else return;
        event.preventDefault();
        this.setPosition(value);
      });
      if ("IntersectionObserver" in window) {
        this.observer = new IntersectionObserver(entries => {
          this.inViewport = entries[0].isIntersecting;
          if (!this.active()) this.pauseHidden();
          else if (!this.manuallyPaused && !this.reducedMotion) this.play();
        }, { threshold: 0.15 });
        this.observer.observe(container);
      } else this.inViewport = true;
      document.addEventListener("scenechange", () => {
        if (this.container.closest("[hidden]")) this.pauseHidden();
      });
      document.addEventListener("visibilitychange", () => {
        if (document.hidden) this.pauseHidden();
        else if (this.active() && !this.manuallyPaused && !this.reducedMotion) this.play();
      });
    }
    active() {
      return this.inViewport && !document.hidden && !this.container.closest("[hidden]");
    }
    pauseHidden() {
      this.video.pause();
      this.stopLoop();
    }
    async play() {
      if (!this.video.paused) return;
      this.container.classList.add("is-loading");
      try {
        await this.video.play();
        if (!this.active()) this.pauseHidden();
      } catch (error) {
        this.container.classList.remove("is-loading");
        if (error.name !== "AbortError") this.status.textContent = "Press Play to start the comparison.";
      }
    }
    resize() {
      const width = this.video.videoWidth / 2, height = this.video.videoHeight;
      if (width && height && (this.canvas.width !== width || this.canvas.height !== height)) {
        this.canvas.width = width;
        this.canvas.height = height;
      }
    }
    setPosition(value) {
      this.position = Math.max(0, Math.min(1, value));
      this.canvas.setAttribute("aria-valuenow", String(Math.round(this.position * 100)));
      this.canvas.setAttribute("aria-valuetext", Math.round(this.position * 100) + "% comparison method");
      this.draw();
    }
    pointer(event) {
      const bounds = this.canvas.getBoundingClientRect();
      if (bounds.width) this.setPosition((event.clientX - bounds.left) / bounds.width);
    }
    draw() {
      if (this.video.readyState < 2 || !this.video.videoWidth) return;
      this.resize();
      const w = this.canvas.width, h = this.canvas.height, x = w * this.position;
      const ctx = this.context, rightWidth = w - x;
      // Original compositing: one full left frame, then the matching right crop.
      ctx.drawImage(this.video, 0, 0, w, h, 0, 0, w, h);
      if (rightWidth > 0) ctx.drawImage(this.video, x + w, 0, rightWidth, h, x, 0, rightWidth, h);
      ctx.strokeStyle = "rgba(255,255,255,.95)";
      ctx.lineWidth = 2;
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
      const y = h / 2, arrowWidth = h / 70, arrowLength = h / 150, offset = h / 150;
      for (const direction of [-1, 1]) {
        ctx.beginPath();
        ctx.moveTo(x + direction * (arrowLength + offset), y - arrowWidth / 2);
        ctx.lineTo(x + direction * (2 * arrowLength + offset), y);
        ctx.lineTo(x + direction * (arrowLength + offset), y + arrowWidth / 2);
        ctx.stroke();
      }
      this.lastTime = this.video.currentTime;
    }
    startLoop() {
      this.stopLoop();
      const tick = () => {
        this.raf = null;
        if (this.video.paused || !this.active()) return;
        if (this.video.currentTime !== this.lastTime) this.draw();
        this.raf = requestAnimationFrame(tick);
      };
      tick();
    }
    stopLoop() {
      if (this.raf !== null) cancelAnimationFrame(this.raf);
      this.raf = null;
    }
  }
  document.querySelectorAll("[data-video-comparison]").forEach(container => new VideoComparison(container));
})();
