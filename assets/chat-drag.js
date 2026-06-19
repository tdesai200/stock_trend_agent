(function () {
  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function setDefaultChatWindowPosition(modal) {
    if (!modal || modal.dataset.positioned === "true") {
      return;
    }

    modal.style.left = "auto";
    modal.style.top = "auto";
    modal.style.right = "20px";
    modal.style.bottom = "90px";
  }

  function initDragChat() {
    var modal = document.getElementById("chat-modal-container");
    var header = document.getElementById("chat-modal-header");
    if (!modal || !header) {
      return;
    }

    setDefaultChatWindowPosition(modal);

    if (header.dataset.dragInitialized === "true") {
      return;
    }
    header.dataset.dragInitialized = "true";

    var isDragging = false;
    var offsetX = 0;
    var offsetY = 0;

    header.addEventListener("mousedown", function (event) {
      isDragging = true;
      var rect = modal.getBoundingClientRect();
      offsetX = event.clientX - rect.left;
      offsetY = event.clientY - rect.top;
      modal.classList.add("chat-modal-dragging");
      header.style.cursor = "grabbing";
      modal.dataset.positioned = "true";
      event.preventDefault();
    });

    document.addEventListener("mousemove", function (event) {
      if (!isDragging) {
        return;
      }

      var maxLeft = window.innerWidth - modal.offsetWidth - 8;
      var maxTop = window.innerHeight - modal.offsetHeight - 8;
      var nextLeft = clamp(event.clientX - offsetX, 8, Math.max(8, maxLeft));
      var nextTop = clamp(event.clientY - offsetY, 8, Math.max(8, maxTop));

      modal.style.left = nextLeft + "px";
      modal.style.top = nextTop + "px";
      modal.style.right = "auto";
      modal.style.bottom = "auto";
    });

    document.addEventListener("mouseup", function () {
      if (!isDragging) {
        return;
      }

      isDragging = false;
      modal.classList.remove("chat-modal-dragging");
      header.style.cursor = "grab";
    });
  }

  document.addEventListener("DOMContentLoaded", initDragChat);
  document.addEventListener("click", function () {
    setTimeout(initDragChat, 0);
  });
  window.addEventListener("resize", function () {
    var modal = document.getElementById("chat-modal-container");
    if (modal && modal.style.display !== "none" && modal.dataset.positioned !== "true") {
      setDefaultChatWindowPosition(modal);
    }
  });
})();
