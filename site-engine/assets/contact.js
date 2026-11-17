/*
  Contact form: sends the message through Web3Forms (https://web3forms.com)
  and shows a confirmation, or a clear message if something goes wrong.
*/
(function () {
  "use strict";

  var form = document.getElementById("contact-form");
  if (!form) return;
  var done = document.getElementById("contact-done");
  var error = document.getElementById("contact-error");
  var again = document.getElementById("contact-again");
  var button = form.querySelector(".send");
  var label = button.querySelector("span");
  var key = form.getAttribute("data-key") || "";
  var demo = form.hasAttribute("data-demo");

  function showError(text) {
    error.textContent = text;
    error.hidden = false;
  }

  function send(data) {
    if (demo) {
      // used only in previews: pretends the message was sent
      return new Promise(function (resolve) { setTimeout(function () { resolve({ success: true }); }, 700); });
    }
    return fetch("https://api.web3forms.com/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(data)
    }).then(function (response) {
      return response.json().catch(function () { return { success: false }; });
    });
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    error.hidden = true;
    if (!key && !demo) {
      showError("The contact form isn't set up yet.");
      return;
    }
    var fields = new FormData(form);
    if (fields.get("botcheck")) return;   // filled in only by spam robots

    var topic = fields.get("topic");
    var data = {
      access_key: key,
      subject: "Message from your website: " + topic,
      name: fields.get("name"),
      email: fields.get("email"),
      topic: topic,
      message: fields.get("message")
    };

    button.disabled = true;
    label.textContent = "Sending…";
    send(data)
      .then(function (result) {
        if (result && result.success) {
          form.reset();
          form.hidden = true;
          done.hidden = false;
          done.focus();
        } else {
          showError("Sorry, your message couldn't be sent. Please try again in a few minutes.");
        }
      })
      .catch(function () {
        showError("Sorry, your message couldn't be sent. Please check your internet connection and try again.");
      })
      .then(function () {
        button.disabled = false;
        label.textContent = "Send message";
      });
  });

  again.addEventListener("click", function () {
    done.hidden = true;
    form.hidden = false;
    form.querySelector("input").focus();
  });
})();
