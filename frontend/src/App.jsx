import { useState, useRef, useEffect } from 'react'
import './index.css'

// WebSocket URL (will be updated for production)
const WS_URL = import.meta.env.PROD 
  ? 'wss://project-home.up.railway.app/ws'
  : 'ws://localhost:8000/ws'

function App() {
  const [isListening, setIsListening] = useState(false)
  const [isConnected, setIsConnected] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [response, setResponse] = useState('')
  const [isProcessing, setIsProcessing] = useState(false)
  
  const wsRef = useRef(null)
  const mediaRecorderRef = useRef(null)
  const audioChunksRef = useRef([])
  const audioContextRef = useRef(null)
  const audioQueueRef = useRef([])
  const isPlayingRef = useRef(false)

  useEffect(() => {
    // Initialize WebSocket connection
    connectWebSocket()
    
    // Initialize audio context (lazy init on user interaction to avoid browser restrictions)
    const initAudioContext = () => {
      if (!audioContextRef.current) {
        try {
          audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)()
          // Resume context if it's suspended (Chrome autoplay policy)
          if (audioContextRef.current.state === 'suspended') {
            audioContextRef.current.resume()
          }
        } catch (e) {
          console.error('Failed to create audio context:', e)
        }
      }
    }
    
    // Init on first user interaction
    document.addEventListener('click', initAudioContext, { once: true })
    
    return () => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.close(1000, 'Component unmounting')
      }
      if (audioContextRef.current?.state !== 'closed') {
        audioContextRef.current?.close()
      }
      document.removeEventListener('click', initAudioContext)
    }
  }, [])

  const connectWebSocket = () => {
    // Prevent multiple connection attempts
    if (wsRef.current?.readyState === WebSocket.CONNECTING) {
      return
    }
    
    try {
      wsRef.current = new WebSocket(WS_URL)
      
      wsRef.current.onopen = () => {
        console.log('WebSocket connected')
        setIsConnected(true)
      }
      
      wsRef.current.onmessage = async (event) => {
        if (typeof event.data === 'string') {
          // JSON message
          try {
            const data = JSON.parse(event.data)
            
            switch (data.type) {
              case 'transcription':
                setTranscript(data.text)
                break
              case 'response':
                setResponse(data.text)
                break
              case 'complete':
                setIsProcessing(false)
                playAudioQueue()
                break
              case 'error':
                console.error('Error:', data.message)
                setIsProcessing(false)
                break
            }
          } catch (e) {
            console.error('Failed to parse message:', e)
          }
        } else {
          // Binary audio data
          audioQueueRef.current.push(event.data)
        }
      }
      
      wsRef.current.onclose = (event) => {
        console.log('WebSocket disconnected:', event.code, event.reason)
        setIsConnected(false)
        wsRef.current = null
        // Attempt to reconnect after 3 seconds (unless intentionally closed)
        if (event.code !== 1000) {
          setTimeout(connectWebSocket, 3000)
        }
      }
      
      wsRef.current.onerror = (error) => {
        console.error('WebSocket error:', error)
      }
    } catch (error) {
      console.error('Failed to connect:', error)
      setTimeout(connectWebSocket, 3000)
    }
  }

  const playAudioQueue = async () => {
    if (isPlayingRef.current || audioQueueRef.current.length === 0) {
      return
    }
    
    isPlayingRef.current = true
    
    while (audioQueueRef.current.length > 0) {
      const audioData = audioQueueRef.current.shift()
      await playAudioChunk(audioData)
    }
    
    isPlayingRef.current = false
  }

  const playAudioChunk = async (audioData) => {
    try {
      const arrayBuffer = await audioData.arrayBuffer()
      const audioBuffer = await audioContextRef.current.decodeAudioData(arrayBuffer)
      
      const source = audioContextRef.current.createBufferSource()
      source.buffer = audioBuffer
      source.connect(audioContextRef.current.destination)
      
      return new Promise((resolve) => {
        source.onended = resolve
        source.start(0)
      })
    } catch (error) {
      console.error('Error playing audio:', error)
    }
  }

  const startListening = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      
      mediaRecorderRef.current = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus'
      })
      
      audioChunksRef.current = []
      
      mediaRecorderRef.current.ondataavailable = (event) => {
        audioChunksRef.current.push(event.data)
      }
      
      mediaRecorderRef.current.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' })
        const arrayBuffer = await audioBlob.arrayBuffer()
        
        // Send audio to server
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          setIsProcessing(true)
          wsRef.current.send(arrayBuffer)
        }
        
        // Clear for next recording
        audioChunksRef.current = []
      }
      
      mediaRecorderRef.current.start()
      setIsListening(true)
    } catch (error) {
      console.error('Error accessing microphone:', error)
    }
  }

  const stopListening = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop()
      mediaRecorderRef.current.stream.getTracks().forEach(track => track.stop())
      setIsListening(false)
    }
  }

  const toggleListening = () => {
    if (isListening) {
      stopListening()
    } else {
      startListening()
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-8">
      {/* Crystal Geode Background Effect */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -left-40 w-80 h-80 bg-purple-500 rounded-full mix-blend-multiply filter blur-xl opacity-30 animate-pulse"></div>
        <div className="absolute -bottom-40 -right-40 w-80 h-80 bg-blue-500 rounded-full mix-blend-multiply filter blur-xl opacity-30 animate-pulse-slow"></div>
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-indigo-500 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-pulse"></div>
      </div>

      {/* Main Content */}
      <div className="relative z-10 max-w-2xl w-full">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-6xl font-bold text-white mb-4 drop-shadow-lg">
            Project Home
          </h1>
          <p className="text-xl text-white/80">
            Talk directly with Hamm
          </p>
        </div>

        {/* Crystal Container */}
        <div className="relative">
          <div className="absolute inset-0 bg-gradient-to-r from-purple-400 to-blue-400 rounded-3xl blur-xl opacity-50"></div>
          <div className="relative bg-white/10 backdrop-blur-xl rounded-3xl p-8 border border-white/20 crystal-glow">
            
            {/* Status Indicator */}
            <div className="flex items-center justify-center mb-8">
              <div className={`flex items-center space-x-2 px-4 py-2 rounded-full ${
                isConnected ? 'bg-green-500/20 border border-green-400/50' : 'bg-red-500/20 border border-red-400/50'
              }`}>
                <div className={`w-2 h-2 rounded-full ${
                  isConnected ? 'bg-green-400 animate-pulse' : 'bg-red-400'
                }`}></div>
                <span className="text-white text-sm">
                  {isConnected ? 'Connected' : 'Connecting...'}
                </span>
              </div>
            </div>

            {/* Voice Button */}
            <div className="flex justify-center mb-8">
              <button
                onClick={toggleListening}
                disabled={!isConnected || isProcessing}
                className={`relative group ${
                  isListening 
                    ? 'bg-red-500 hover:bg-red-600' 
                    : 'bg-gradient-to-r from-purple-500 to-blue-500 hover:from-purple-600 hover:to-blue-600'
                } text-white rounded-full p-8 transition-all transform hover:scale-105 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                <div className="absolute inset-0 rounded-full bg-white/20 scale-110 animate-ping"></div>
                {isListening ? (
                  <svg className="w-12 h-12" fill="currentColor" viewBox="0 0 20 20">
                    <rect x="6" y="4" width="3" height="12" rx="1" />
                    <rect x="11" y="4" width="3" height="12" rx="1" />
                  </svg>
                ) : (
                  <svg className="w-12 h-12" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M7 4a3 3 0 016 0v4a3 3 0 11-6 0V4zm4 10.93A7.001 7.001 0 0017 8a1 1 0 10-2 0A5 5 0 015 8a1 1 0 00-2 0 7.001 7.001 0 006 6.93V17H6a1 1 0 100 2h8a1 1 0 100-2h-3v-2.07z" clipRule="evenodd" />
                  </svg>
                )}
              </button>
            </div>

            {/* Status Text */}
            <div className="text-center mb-6">
              <p className="text-white/60 text-sm">
                {isProcessing ? 'Processing...' : 
                 isListening ? 'Listening... Click to stop' : 
                 'Click to start talking'}
              </p>
            </div>

            {/* Transcript & Response */}
            <div className="space-y-4">
              {transcript && (
                <div className="bg-white/5 rounded-xl p-4 border border-white/10">
                  <p className="text-white/60 text-xs uppercase tracking-wider mb-2">You said:</p>
                  <p className="text-white">{transcript}</p>
                </div>
              )}
              
              {response && (
                <div className="bg-white/5 rounded-xl p-4 border border-white/10 geode-shimmer">
                  <p className="text-white/60 text-xs uppercase tracking-wider mb-2">Hamm:</p>
                  <p className="text-white">{response}</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="text-center mt-8">
          <p className="text-white/40 text-sm">
            Voice interface powered by Groq Whisper & ElevenLabs Ivy
          </p>
        </div>
      </div>
    </div>
  )
}

export default App