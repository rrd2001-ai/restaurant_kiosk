
(() => {
  // --------------------------------------------------
  // STATE
  // --------------------------------------------------

  let sessionId = null;
  let speechEnabled = true;
  let sending = false;
  let checkoutPending = false;
  let orderConfirmed = false;

  let handsFreeEnabled = false;
  let speaking = false;
  let processingSpeech = false;

  let mediaStream = null;
  let mediaRecorder = null;
  let audioContext = null;
  let analyser = null;
  let microphoneSource = null;

  let audioChunks = [];
  let animationFrame = null;

  let speechStarted = false;
  let speechStartTime = 0;
  let lastSoundTime = 0;

  let currentAudio = null;
  let speechToken = 0;

  const SILENCE_DURATION = 1200;
  const MAX_RECORDING_DURATION = 12000;
  const SPEECH_THRESHOLD = 0.025;
  const MIN_SPEECH_DURATION = 350;

  const $ = id => document.getElementById(id);

  const chatBox = $('chatBox');
  const input = $('messageInput');
  const sendButton = $('sendButton');

  const greeting =
    'Hello! Welcome to Namma Veedu. What would you like to order today?';


  // --------------------------------------------------
  // CHAT UI
  // --------------------------------------------------

  function message(text, who = 'assistant') {
    const el = document.createElement('div');

    el.className = `message ${who}`;
    el.textContent = text;

    chatBox.appendChild(el);
    chatBox.scrollTop = chatBox.scrollHeight;
  }


  function updateVoiceControls() {
    $('voiceButton').textContent = handsFreeEnabled
      ? '🎙️ Hands-free mode on'
      : '🎙️ Enable hands-free';

    $('stopVoiceButton').disabled = !handsFreeEnabled;
  }


  function updateVoiceStatus(text) {
    $('voiceStatus').textContent = text;
  }


  // --------------------------------------------------
  // API
  // --------------------------------------------------

  async function api(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(data.detail || 'Request failed');
    }

    return data;
  }


  function busy(value) {
    sending = value;

    sendButton.disabled = value;
    input.disabled = value;

    sendButton.textContent = value ? 'Sending…' : 'Send';
  }


  // --------------------------------------------------
  // PIPER TEXT TO SPEECH
  // --------------------------------------------------

  async function speak(text) {
    if (!speechEnabled || !handsFreeEnabled) {
      speaking = false;
      return;
    }

    const token = ++speechToken;

    speaking = true;
    updateVoiceStatus('Preparing voice response…');

    try {
      const response = await fetch('/api/speech/synthesize', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text }),
      });

      if (!response.ok) {
        throw new Error('Speech generation failed');
      }

      const audioBlob = await response.blob();

      if (token !== speechToken) return;

      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);

      currentAudio = audio;

      try {
        await audio.play();

        updateVoiceStatus('Speaking…');

        await new Promise((resolve, reject) => {
          audio.onended = resolve;

          audio.onerror = () => {
            reject(new Error('Audio playback failed'));
          };
        });
      } finally {
        URL.revokeObjectURL(audioUrl);

        if (currentAudio === audio) {
          currentAudio = null;
        }
      }
    } catch (error) {
      console.error('Piper TTS error:', error);

      if (token === speechToken) {
        updateVoiceStatus(
          'Voice response unavailable. You can still read the reply.'
        );
      }
    } finally {
      if (token === speechToken) {
        speaking = false;

        if (handsFreeEnabled && !sending && !processingSpeech) {
          startCaptureCycle();
        }
      }
    }
  }


  async function assistant(text) {
    message(text);

    if (speechEnabled && handsFreeEnabled) {
      await speak(text);
    }
  }


  // --------------------------------------------------
  // CART
  // --------------------------------------------------

  function renderCart(cart) {
    const host = $('cartItems');

    host.replaceChildren();

    if (!cart?.items?.length) {
      const p = document.createElement('p');

      p.className = 'empty';
      p.textContent = 'Your cart is empty.';

      host.append(p);
    } else {
      cart.items.forEach(item => {
        const row = document.createElement('div');
        row.className = 'cart-row';

        const info = document.createElement('div');

        const name = document.createElement('strong');
        const small = document.createElement('small');

        name.textContent = item.name;

        small.textContent =
          `₹${item.price} × ${item.quantity} = ₹${item.subtotal}`;

        info.append(name, small);

        const actions = document.createElement('div');
        actions.className = 'cart-actions';

        const minus = document.createElement('button');
        minus.className = 'button secondary';
        minus.textContent = '−';
        minus.disabled = checkoutPending || orderConfirmed;
        minus.onclick = () => changeItem(item.id, -1);

        const plus = document.createElement('button');
        plus.className = 'button secondary';
        plus.textContent = '+';
        plus.disabled = checkoutPending || orderConfirmed;
        plus.onclick = () => changeItem(item.id, 1);

        actions.append(minus, plus);
        row.append(info, actions);

        host.append(row);
      });
    }

    $('cartTotal').textContent = `₹${cart?.total ?? 0}`;
    $('cartCount').textContent = `${cart?.count ?? 0} items`;

    $('finishOrderButton').disabled =
      !cart?.items?.length || checkoutPending || orderConfirmed;

    document.querySelectorAll('.add-button').forEach(button => {
      button.disabled = checkoutPending || orderConfirmed;
    });
  }


  async function changeItem(id, delta) {
    try {
      const data = await api(
        `/api/cart/${delta > 0 ? 'add' : 'remove'}`,
        {
          method: 'POST',
          body: JSON.stringify({
            session_id: sessionId,
            item_id: id,
            quantity: 1,
          }),
        }
      );

      renderCart(data.cart);

      if (delta > 0) {
        const item = menuItems.find(x => x.id === id);

        if (item) {
          void assistant(
            `Added ${item.name}. Would you like anything else?`
          );
        }
      }
    } catch (error) {
      message(error.message);
    }
  }


  // --------------------------------------------------
  // MENU
  // --------------------------------------------------

  let menuItems = [];


  async function loadMenu() {
    const data = await api('/api/menu');

    menuItems = data.items;

    const grid = $('menuGrid');

    grid.replaceChildren();

    menuItems.forEach(item => {
      const card = document.createElement('article');
      card.className = 'menu-item';

      const heading = document.createElement('h3');
      heading.textContent = item.name;

      const category = document.createElement('div');
      category.className = 'category';
      category.textContent = item.category || 'Menu';

      const description = document.createElement('p');
      description.className = 'description';
      description.textContent = item.description || '';

      const price = document.createElement('div');
      price.className = 'price';
      price.textContent = `₹${item.price}`;

      const button = document.createElement('button');

      button.className = 'button primary add-button';
      button.textContent = 'Add to order';
      button.onclick = () => changeItem(item.id, 1);

      card.append(
        heading,
        category,
        description,
        price,
        button
      );

      grid.append(card);
    });
  }


  // --------------------------------------------------
  // SESSION
  // --------------------------------------------------

  async function startSession() {
    const data = await api('/api/session', {
      method: 'POST',
      body: JSON.stringify({}),
    });

    sessionId = data.session_id;

    renderCart(data.cart);
  }


  // --------------------------------------------------
  // CONVERSATION
  // --------------------------------------------------

  async function send(text) {
    text = text.trim();

    if (!text || sending || !sessionId) return;

    if (orderConfirmed) {
      await assistant(
        'This order is already confirmed. Please start a new order.'
      );
      return;
    }

    // Pause microphone capture while handling a request.
    stopCaptureCycle();

    message(text, 'user');

    input.value = '';

    busy(true);

    try {
      const data = await api('/api/conversation', {
        method: 'POST',
        body: JSON.stringify({
          session_id: sessionId,
          text,
        }),
      });

      renderCart(data.cart);

      checkoutPending = !!data.checkout_pending;

      $('checkoutBox').classList.toggle(
        'hidden',
        !checkoutPending
      );

      if (data.action === 'confirm_checkout' && data.receipt) {
        orderConfirmed = true;
        checkoutPending = false;

        $('checkoutBox').classList.add('hidden');

        $('receiptAnchor').href = data.receipt.receipt_url;
        $('receiptLink').classList.remove('hidden');

        renderCart(data.cart);
      }

      // Wait for speech playback before resuming the microphone.
      await assistant(data.message || 'How else can I help?');
    } catch (error) {
      message(`Error: ${error.message}`);
    } finally {
      busy(false);

      if (handsFreeEnabled && !speaking && !processingSpeech) {
        startCaptureCycle();
      }
    }
  }


  // --------------------------------------------------
  // MICROPHONE RECORDING
  // --------------------------------------------------

  function getSupportedMimeType() {
    const types = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/mp4',
    ];

    for (const type of types) {
      if (window.MediaRecorder?.isTypeSupported(type)) {
        return type;
      }
    }

    return '';
  }


  async function enableMicrophone() {
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error(
        'Microphone access is not supported in this browser.'
      );
    }

    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });

    audioContext = new (
      window.AudioContext || window.webkitAudioContext
    )();

    await audioContext.resume();

    analyser = audioContext.createAnalyser();
    analyser.fftSize = 2048;
    analyser.smoothingTimeConstant = 0.2;

    microphoneSource =
      audioContext.createMediaStreamSource(mediaStream);

    microphoneSource.connect(analyser);
  }


  function stopCaptureCycle() {
    if (animationFrame !== null) {
      cancelAnimationFrame(animationFrame);
      animationFrame = null;
    }

    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.onstop = null;

      try {
        mediaRecorder.stop();
      } catch (error) {
        console.warn(error);
      }
    }

    mediaRecorder = null;
    audioChunks = [];

    speechStarted = false;
  }


  function startCaptureCycle() {
    if (
      !handsFreeEnabled ||
      !mediaStream ||
      !analyser ||
      sending ||
      speaking ||
      processingSpeech ||
      orderConfirmed ||
      mediaRecorder
    ) {
      return;
    }

    if (!window.MediaRecorder) {
      updateVoiceStatus(
        'Audio recording is not supported in this browser.'
      );
      return;
    }

    try {
      const mimeType = getSupportedMimeType();

      mediaRecorder = mimeType
        ? new MediaRecorder(mediaStream, { mimeType })
        : new MediaRecorder(mediaStream);

      audioChunks = [];
      speechStarted = false;

      const dataType = mediaRecorder.mimeType || mimeType;

      mediaRecorder.ondataavailable = event => {
        if (event.data && event.data.size > 0) {
          audioChunks.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const chunks = audioChunks;
        audioChunks = [];
        mediaRecorder = null;

        if (
          !handsFreeEnabled ||
          !speechStarted ||
          !chunks.length
        ) {
          return;
        }

        const blob = new Blob(chunks, {
          type: dataType || 'application/octet-stream',
        });

        await processRecordedSpeech(blob);
      };

      mediaRecorder.start();

      updateVoiceStatus('Listening…');

      monitorMicrophone();
    } catch (error) {
      console.error('Recording error:', error);

      updateVoiceStatus(
        `Could not start recording: ${error.message}`
      );

      mediaRecorder = null;
    }
  }


  // --------------------------------------------------
  // SILENCE DETECTION
  // --------------------------------------------------

  function monitorMicrophone() {
    if (!handsFreeEnabled || !analyser || !mediaRecorder) {
      return;
    }

    const samples = new Uint8Array(analyser.fftSize);

    const checkAudio = () => {
      if (
        !handsFreeEnabled ||
        !analyser ||
        !mediaRecorder ||
        mediaRecorder.state !== 'recording'
      ) {
        return;
      }

      analyser.getByteTimeDomainData(samples);

      let sum = 0;

      for (let i = 0; i < samples.length; i++) {
        const normalized = (samples[i] - 128) / 128;
        sum += normalized * normalized;
      }

      const rms = Math.sqrt(sum / samples.length);
      const now = Date.now();

      if (rms > SPEECH_THRESHOLD) {
        if (!speechStarted) {
          speechStarted = true;
          speechStartTime = now;
          updateVoiceStatus('Hearing you…');
        }

        lastSoundTime = now;
      }

      if (speechStarted) {
        const recordingDuration = now - speechStartTime;
        const silenceDuration = now - lastSoundTime;

        if (
          recordingDuration >= MAX_RECORDING_DURATION ||
          (
            recordingDuration >= MIN_SPEECH_DURATION &&
            silenceDuration >= SILENCE_DURATION
          )
        ) {
          if (animationFrame !== null) {
            cancelAnimationFrame(animationFrame);
            animationFrame = null;
          }

          if (mediaRecorder.state === 'recording') {
            mediaRecorder.stop();
          }

          return;
        }
      }

      animationFrame = requestAnimationFrame(checkAudio);
    };

    animationFrame = requestAnimationFrame(checkAudio);
  }


  // --------------------------------------------------
  // SHERPA SPEECH RECOGNITION
  // --------------------------------------------------

  async function processRecordedSpeech(blob) {
    if (
      !handsFreeEnabled ||
      sending ||
      processingSpeech
    ) {
      return;
    }

    processingSpeech = true;

    updateVoiceStatus('Recognizing your speech…');

    try {
      const formData = new FormData();

      formData.append('audio', blob, 'order-recording.webm');

      const response = await fetch('/api/speech/transcribe', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          data.detail || 'Speech recognition failed.'
        );
      }

      const transcript = (data.text || '').trim();

      if (!transcript) {
        updateVoiceStatus(
          'I could not hear that clearly. Please try again.'
        );
        return;
      }

      updateVoiceStatus(`Heard: ${transcript}`);

      // Send recognized speech through the existing AI waiter.
      processingSpeech = false;

      await send(transcript);
    } catch (error) {
      console.error('Speech recognition error:', error);

      updateVoiceStatus(error.message);
    } finally {
      processingSpeech = false;

      if (
        handsFreeEnabled &&
        !sending &&
        !speaking &&
        !mediaRecorder
      ) {
        startCaptureCycle();
      }
    }
  }


  // --------------------------------------------------
  // HANDS-FREE CONTROLS
  // --------------------------------------------------

  async function enableHandsFree() {
    if (handsFreeEnabled) return;

    if (!window.MediaRecorder) {
      updateVoiceStatus(
        'Your browser does not support microphone recording.'
      );
      return;
    }

    try {
      updateVoiceStatus('Requesting microphone permission…');

      await enableMicrophone();

      handsFreeEnabled = true;

      updateVoiceControls();

      updateVoiceStatus('Hands-free mode enabled.');

      // The user gesture enables audio playback in the browser.
      if (speechEnabled) {
        await speak(greeting);
      } else {
        startCaptureCycle();
      }
    } catch (error) {
      console.error(error);

      handsFreeEnabled = false;

      updateVoiceControls();

      updateVoiceStatus(
        `Microphone error: ${error.message}`
      );
    }
  }


  function disableHandsFree() {
    handsFreeEnabled = false;

    speechToken++;

    stopCaptureCycle();

    if (currentAudio) {
      currentAudio.pause();
      currentAudio = null;
    }

    speaking = false;
    processingSpeech = false;

    if (mediaStream) {
      mediaStream.getTracks().forEach(track => track.stop());
      mediaStream = null;
    }

    if (audioContext) {
      audioContext.close().catch(console.error);
      audioContext = null;
    }

    analyser = null;
    microphoneSource = null;

    updateVoiceControls();

    updateVoiceStatus('Voice listening stopped.');
  }


  $('voiceButton').onclick = enableHandsFree;

  $('stopVoiceButton').onclick = disableHandsFree;


  // --------------------------------------------------
  // VOICE REPLY TOGGLE
  // --------------------------------------------------

  $('toggleSpeechButton').onclick = () => {
    speechEnabled = !speechEnabled;

    $('toggleSpeechButton').textContent = speechEnabled
      ? '🔊 Voice replies on'
      : '🔇 Voice replies off';

    if (!speechEnabled) {
      speechToken++;

      if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
      }

      speaking = false;

      if (handsFreeEnabled && !sending && !processingSpeech) {
        startCaptureCycle();
      }
    }
  };


  // --------------------------------------------------
  // TEXT INPUT AND CHECKOUT
  // --------------------------------------------------

  $('chatForm').addEventListener('submit', event => {
    event.preventDefault();
    void send(input.value);
  });

  $('finishOrderButton').onclick = () => {
    void send("That's all");
  };

  $('confirmCheckoutButton').onclick = () => {
    void send('Yes, confirm my order');
  };

  $('cancelCheckoutButton').onclick = () => {
    void send('No, I want to continue ordering');
  };


  // --------------------------------------------------
  // NEW ORDER
  // --------------------------------------------------

  $('newOrder').onclick = async () => {
    if (
      !confirm(
        'Start a new order? The current cart will remain saved in order history but will not be carried over.'
      )
    ) {
      return;
    }

    try {
      stopCaptureCycle();

      await startSession();

      checkoutPending = false;
      orderConfirmed = false;

      $('checkoutBox').classList.add('hidden');
      $('receiptLink').classList.add('hidden');

      chatBox.replaceChildren();

      await assistant(
        'Welcome back! What would you like to order?'
      );

      if (handsFreeEnabled && !speaking) {
        startCaptureCycle();
      }
    } catch (error) {
      message(error.message);
    }
  };


  // --------------------------------------------------
  // INITIALIZE
  // --------------------------------------------------

  Promise.all([
    loadMenu(),
    startSession(),
  ])
    .then(() => {
      message(greeting);

      updateVoiceControls();

      updateVoiceStatus(
        'Click Enable hands-free once to start voice ordering.'
      );
    })
    .catch(error => {
      message(`Could not start kiosk: ${error.message}`);
    });

})();
