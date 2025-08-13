# Hand Gestures and Voice Controlled Computer System - Setup Guide

## 🚀 Quick Start

### Prerequisites
- **Python 3.8+** installed on your system
- **Webcam** for hand gesture recognition
- **Microphone** for voice commands
- **Windows 10/11** (primary support)

### 1. Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd Hand-Gestures-And-Voice-Controlled-Computer-System

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration

1. **Copy the environment template:**
   ```bash
   copy env.example .env
   ```

2. **Get your AssemblyAI API Key:**
   - Go to [AssemblyAI](https://www.assemblyai.com/)
   - Sign up for a free account
   - Copy your API key from the dashboard

3. **Update your `.env` file:**
   ```env
   ASSEMBLYAI_API_KEY=your_actual_api_key_here
   ```

### 3. Run the Application

```bash
python HV_SYSTEM.py
```

## 🔧 Configuration Options

### Audio Settings
- `FRAME_PER_BUFFER`: Audio buffer size (default: 3200)
- `AUDIO_CHANNELS`: Number of audio channels (default: 1)
- `AUDIO_RATE`: Audio sample rate (default: 16000)

### Hand Tracking Settings
- `MAX_HANDS`: Maximum hands to detect (default: 1)
- `DETECTION_CONFIDENCE`: Detection confidence threshold (default: 0.5)
- `TRACKING_CONFIDENCE`: Tracking confidence threshold (default: 0.5)
- `SMOOTHENING_FACTOR`: Mouse movement smoothening (default: 7)

### System Settings
- `DEBUG_MODE`: Enable debug logging (default: False)
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)

## 🎮 Usage Modes

### Hand Gesture Only Mode
- Control mouse pointer with hand gestures
- No voice commands required
- Perfect for quiet environments

### Hand & Voice Combined Mode
- Full system control with both modalities
- Voice commands for complex operations
- Hand gestures for precise mouse control

## 🛡️ Security Features

### ✅ What's Improved (v2.0.0)
- ✅ **Secure API Key Management**: No more hardcoded secrets
- ✅ **Input Validation**: All voice commands are sanitized
- ✅ **Safe Command Execution**: Whitelist-based system command validation
- ✅ **Dynamic Application Discovery**: Automatically finds installed apps
- ✅ **Comprehensive Logging**: Track all system activities
- ✅ **Error Handling**: Robust error management

### 🔒 Security Guidelines
1. **Never share your `.env` file**
2. **Keep your AssemblyAI API key private**
3. **Review logs regularly** in the `logs/` directory
4. **Update dependencies** regularly for security patches

## 📁 Project Structure

```
Hand-Gestures-And-Voice-Controlled-Computer-System/
├── config/
│   ├── __init__.py
│   └── settings.py          # Configuration management
├── utils/
│   ├── __init__.py
│   ├── logger.py           # Logging utilities
│   ├── security.py         # Security validation
│   └── application_finder.py # Dynamic app discovery
├── user_manual_guides/      # Gesture guide images
├── logs/                   # Application logs (created automatically)
├── HV_SYSTEM.py           # Main application
├── HandTrackingModule.py  # Hand detection module
├── requirements.txt       # Dependencies
├── .env                   # Your environment variables (create this)
├── env.example           # Environment template
└── README.md             # Project overview
```

## 🐛 Troubleshooting

### Common Issues

**1. "ASSEMBLYAI_API_KEY not found"**
```bash
# Solution: Make sure you created .env file and added your API key
copy env.example .env
# Edit .env and add your API key
```

**2. "Camera not detected"**
```bash
# Solution: Check if camera is being used by another application
# Close other applications using camera (Teams, Zoom, etc.)
```

**3. "Microphone permissions"**
```bash
# Solution: Grant microphone permissions
# Windows Settings > Privacy > Microphone > Allow apps to access microphone
```

**4. "Module not found" errors**
```bash
# Solution: Install missing dependencies
pip install -r requirements.txt
```

**5. "Application not found" warnings**
```bash
# Solution: The app will automatically search for installed applications
# Some hardcoded paths may not work - check logs for details
```

### Debug Mode

Enable debug mode for detailed logging:

```env
DEBUG_MODE=True
LOG_LEVEL=DEBUG
```

Check logs in the `logs/` directory for detailed information.

## 📞 Support

- **Logs Location**: `logs/hv_system_YYYYMMDD.log`
- **Configuration Issues**: Check your `.env` file
- **Performance Issues**: Adjust confidence thresholds in settings
- **Security Concerns**: Review `utils/security.py` whitelist

## 🔄 Updates

### Version 2.0.0 Changes
- ✅ Secure configuration management
- ✅ Enhanced security validation
- ✅ Improved error handling
- ✅ Dynamic application discovery
- ✅ Comprehensive logging
- ✅ Modular architecture

### Upcoming Features
- 🔄 Web-based UI interface
- 🔄 Custom gesture training
- 🔄 Multi-language support
- 🔄 Cloud synchronization
- 🔄 Mobile companion app

---

**⚠️ Important**: Always keep your `.env` file private and never commit it to version control!

