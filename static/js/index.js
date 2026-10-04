/* Local, dependency-free interactions for the project page. */
"use strict";
(() => {
  document.querySelectorAll('[role="tablist"]').forEach(list => {
    const tabs = [...list.querySelectorAll('[role="tab"]')];
    const activate = tab => {
      tabs.forEach(item => {
        const active = item === tab;
        item.setAttribute("aria-selected", String(active));
        item.tabIndex = active ? 0 : -1;
        document.getElementById(item.getAttribute("aria-controls")).hidden = !active;
      });
      document.dispatchEvent(new CustomEvent("scenechange"));
    };
    tabs.forEach((tab, i) => {
      tab.addEventListener("click", () => activate(tab));
      tab.addEventListener("keydown", event => {
        let next;
        if (event.key === "ArrowRight") next = (i + 1) % tabs.length;
        else if (event.key === "ArrowLeft") next = (i - 1 + tabs.length) % tabs.length;
        else if (event.key === "Home") next = 0;
        else if (event.key === "End") next = tabs.length - 1;
        if (next !== undefined) {
          event.preventDefault();
          activate(tabs[next]);
          tabs[next].focus();
        }
      });
    });
  });

  const dialog = document.getElementById("figure-dialog");
  const dialogImage = document.getElementById("figure-dialog-image");
  const area = dialog.querySelector(".dialog-image-area");
  const zoom = document.getElementById("figure-zoom");
  document.querySelectorAll("[data-lightbox]").forEach(link => {
    link.addEventListener("click", event => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      if (typeof dialog.showModal !== "function") return;
      event.preventDefault();
      const img = link.querySelector("img");
      dialogImage.src = link.href;
      dialogImage.alt = img.alt;
      document.getElementById("figure-dialog-title").textContent = img.alt;
      document.getElementById("figure-original").href = link.href;
      area.classList.remove("is-zoomed");
      zoom.setAttribute("aria-pressed", "false");
      zoom.textContent = "Actual size";
      dialog.showModal();
    });
  });
  zoom.addEventListener("click", () => {
    const full = area.classList.toggle("is-zoomed");
    zoom.setAttribute("aria-pressed", String(full));
    zoom.textContent = full ? "Fit to window" : "Actual size";
  });
  document.getElementById("figure-close").addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", event => { if (event.target === dialog) dialog.close(); });

  const renderScenes = {
    "Building": ["BGS_building_720p.mp4", "building_BGS.jpg"],
    "Rubble": ["BGS_rubble_720p.mp4", "rubble_BGS.jpg"],
    "Residence": ["BGS_residence_720p.mp4", "residence_BGS.jpg"],
    "MatrixCity-Aerial": ["BGS_mc_aerial_720p.mp4", "MC-aerial_BGS.jpg"],
    "MatrixCity-Street": ["BGS_mc_street_720p.mp4", null]
  };
  const renderVideo = document.getElementById("render-video");
  document.querySelectorAll("[data-render-scene]").forEach(button => {
    button.addEventListener("click", () => {
      if (button.getAttribute("aria-pressed") === "true") return;
      document.querySelectorAll("[data-render-scene]").forEach(b => b.setAttribute("aria-pressed", String(b === button)));
      const scene = button.dataset.renderScene;
      const [video, poster] = renderScenes[scene];
      renderVideo.pause();
      renderVideo.src = "static/videos/" + video;
      if (poster) renderVideo.poster = "static/images/comparison/" + poster;
      else renderVideo.removeAttribute("poster");
      renderVideo.setAttribute("aria-label", "BlockGaussian novel-view rendering of " + scene);
      renderVideo.preload = "metadata";
      renderVideo.load();
      document.getElementById("render-video-caption").textContent = scene + " · BlockGaussian novel-view rendering. Use the player controls to start or pause.";
      document.getElementById("render-status").textContent = "";
    });
  });
  renderVideo.addEventListener("error", () => {
    document.getElementById("render-status").textContent = "This video could not be loaded. Try another scene or reload the page.";
  });

  const imageScenes = {
    "Building": ["building_3DGS.jpg", "building_BGS.jpg", "3DGS"],
    "Residence": ["residence_DOGS.jpg", "residence_BGS.jpg", "DOGS"],
    "MatrixCity-Aerial": ["MC-aerial_CGS.jpg", "MC-aerial_BGS.jpg", "CityGaussian"],
    "Rubble": ["rubble_vast.jpg", "rubble_BGS.jpg", "VastGaussian"]
  };
  // Reuse the original site's DICS comparison, with a focusable divider.
  const comparison = document.getElementById("image-compare");
  const firstImage = comparison.querySelector("img");
  const imageReady = firstImage.decode().then(() => {
    const dics = new Dics({
      container: comparison, textPosition: "bottom",
      arrayBackgroundColorText: ["#000000", "#000000"],
      arrayColorText: ["#FFFFFF", "#FFFFFF"], linesColor: "#ffffff"
    });
    // DICS otherwise has no active divider until the first drag.
    dics._activeSlider = 0;
    const handle = dics.sliders[0];
    handle.tabIndex = 0;
    handle.setAttribute("role", "slider");
    handle.setAttribute("aria-label", "Image comparison divider");
    handle.setAttribute("aria-valuemin", "0");
    handle.setAttribute("aria-valuemax", "100");
    const sync = () => {
      const value = Math.round(parseFloat(handle.style.left) / comparison.clientWidth * 100);
      handle.setAttribute("aria-valuenow", String(value));
      handle.setAttribute("aria-valuetext", value + "% comparison method");
    };
    const setPosition = value => {
      const width = comparison.getBoundingClientRect().width;
      const x = Math.max(0, Math.min(100, value)) / 100 * width;
      const sections = [...dics.sections];
      sections[0].style.flex = "0 0 " + x + "px";
      sections[1].style.flex = "0 0 " + (width - x) + "px";
      sections[1].querySelector("img").style.left = -x + "px";
      handle.style.left = x + "px";
      sync();
    };
    // Keep DICS's handles and pointer/touch events, but use fixed widths for
    // this two-image comparison so flex reflow cannot shift the image origins.
    dics._pushSections = (_delta, position) => {
      setPosition(position / comparison.getBoundingClientRect().width * 100);
    };
    const resize = () => {
      const width = comparison.getBoundingClientRect().width;
      if (!width || !firstImage.naturalWidth) return;
      comparison.style.height = width * firstImage.naturalHeight / firstImage.naturalWidth + "px";
      dics._resetSizes();
      sync();
    };
    // DICS's window resize can run before responsive layout has settled.
    // Observe the final container size so both images keep the same scale.
    if ("ResizeObserver" in window) {
      let previousWidth = 0;
      new ResizeObserver(entries => {
        const {width, height} = entries[0].contentRect;
        const expectedHeight = width * firstImage.naturalHeight / firstImage.naturalWidth;
        if (width !== previousWidth || Math.abs(height - expectedHeight) > 0.5) {
          previousWidth = width;
          resize();
        }
      }).observe(comparison);
    } else window.addEventListener("resize", resize);
    handle.addEventListener("keydown", event => {
      let value = Number(handle.getAttribute("aria-valuenow"));
      if (event.key === "ArrowLeft") value -= 5;
      else if (event.key === "ArrowRight") value += 5;
      else if (event.key === "Home") value = 0;
      else if (event.key === "End") value = 100;
      else return;
      event.preventDefault();
      setPosition(value);
    });
    ["click", "mousemove", "touchmove", "touchend"].forEach(name =>
      comparison.addEventListener(name, sync, {passive: true}));
    window.addEventListener("resize", sync);
    sync();
    return {dics, sync, resize};
  }).catch(() => {
    comparison.style.opacity = "1";
    document.getElementById("image-comparison-caption").textContent = "Comparison images could not be loaded. Reload the page to try again.";
    return null;
  });
  document.querySelectorAll("[data-image-scene]").forEach(button => {
    button.addEventListener("click", async () => {
      const ready = await imageReady;
      if (!ready) return;
      document.querySelectorAll("[data-image-scene]").forEach(b => b.setAttribute("aria-pressed", String(b === button)));
      const scene = button.dataset.imageScene;
      const [before, after, method] = imageScenes[scene];
      const images = comparison.querySelectorAll("img");
      images[0].src = "static/images/comparison/" + before;
      images[1].src = "static/images/comparison/" + after;
      images[0].alt = method;
      images[1].alt = "BlockGaussian";
      const labels = comparison.querySelectorAll(".b-dics__text");
      labels[0].textContent = method;
      labels[1].textContent = "BlockGaussian";
      try {
        await Promise.all([...images].map(image => image.decode()));
      } catch {
        if (button.getAttribute("aria-pressed") === "true") {
          document.getElementById("image-comparison-caption").textContent = "Comparison images could not be loaded. Try another scene or reload the page.";
        }
        return;
      }
      if (button.getAttribute("aria-pressed") !== "true") return;
      ready.resize();
      document.getElementById("image-comparison-caption").textContent =
        "Scene " + scene + ": left is " + method + ", right is BlockGaussian. Drag the divider to compare.";
    });
  });

  if ("IntersectionObserver" in window) {
    new IntersectionObserver(entries => {
      entries.forEach(entry => { if (!entry.isIntersecting) renderVideo.pause(); });
    }, { threshold: 0.1 }).observe(renderVideo);
  }
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) document.querySelectorAll("video").forEach(video => video.pause());
  });

  document.getElementById("copy-bibtex").addEventListener("click", async () => {
    const code = document.getElementById("bibtex");
    const status = document.getElementById("copy-status");
    try {
      if (!navigator.clipboard?.writeText) throw new Error("Clipboard unavailable");
      await navigator.clipboard.writeText(code.textContent);
      status.textContent = "BibTeX copied.";
    } catch {
      const range = document.createRange();
      range.selectNodeContents(code);
      const selection = getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      status.textContent = "Citation selected. Press Ctrl+C (or Command+C) to copy.";
    }
  });
})();
