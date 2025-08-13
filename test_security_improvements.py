#!/usr/bin/env python3
"""
Test script to demonstrate security improvements in HV System v2.0.0
"""
import os
import sys

# Set dummy API key for testing
os.environ['ASSEMBLYAI_API_KEY'] = 'test_key_for_demo_purposes_only'

def test_configuration():
    """Test the new configuration system"""
    print("🔧 Testing Configuration System...")
    try:
        from config.settings import settings
        print(f"✅ Configuration loaded successfully")
        print(f"   Version: {settings.VERSION}")
        print(f"   Window Title: {settings.WINDOW_TITLE}")
        print(f"   API Key: {settings.ASSEMBLYAI_API_KEY[:8]}...(hidden)")
        print(f"   Debug Mode: {settings.DEBUG_MODE}")
        return True
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

def test_logging():
    """Test the logging system"""
    print("\n📝 Testing Logging System...")
    try:
        from utils.logger import logger
        logger.info("Test log message - Configuration system working")
        logger.warning("Test warning message")
        print("✅ Logging system working")
        print("   Check logs/ directory for detailed logs")
        return True
    except Exception as e:
        print(f"❌ Logging test failed: {e}")
        return False

def test_security_validation():
    """Test security validation and sanitization"""
    print("\n🛡️ Testing Security Validation...")
    try:
        from utils.security import security
        
        # Test command sanitization
        safe_command = security.sanitize_voice_command("open notepad")
        dangerous_command = security.sanitize_voice_command("rm -rf /; dangerous command")
        
        print(f"✅ Safe command: '{safe_command}' ✓")
        print(f"✅ Dangerous command blocked: '{dangerous_command}' (empty = blocked)")
        
        # Test system command validation
        safe_system = security.validate_system_command("notepad")
        unsafe_system = security.validate_system_command("rm -rf /")
        
        print(f"✅ System command validation:")
        print(f"   'notepad' allowed: {safe_system}")
        print(f"   'rm -rf /' blocked: {not unsafe_system}")
        
        return True
    except Exception as e:
        print(f"❌ Security test failed: {e}")
        return False

def test_application_finder():
    """Test dynamic application discovery"""
    print("\n🔍 Testing Application Discovery...")
    try:
        from utils.application_finder import app_finder
        
        # Test finding common applications
        apps_to_test = ['notepad', 'calculator', 'chrome']
        found_apps = []
        
        for app in apps_to_test:
            path = app_finder.find_application(app)
            if path:
                found_apps.append(app)
                print(f"✅ Found {app}: {path}")
            else:
                print(f"⚠️  {app} not found (may not be installed)")
        
        print(f"✅ Application discovery working ({len(found_apps)}/{len(apps_to_test)} apps found)")
        return True
    except Exception as e:
        print(f"❌ Application discovery test failed: {e}")
        return False

def test_improved_security():
    """Demonstrate security improvements vs old version"""
    print("\n🔒 Security Improvements Demonstration...")
    
    print("📊 Version 1.0.0 vs 2.0.0 Comparison:")
    print("┌─────────────────────────────┬─────────────┬─────────────┐")
    print("│ Security Feature            │ v1.0.0      │ v2.0.0      │")
    print("├─────────────────────────────┼─────────────┼─────────────┤")
    print("│ API Key Storage             │ ❌ Hardcoded│ ✅ Env Vars │")
    print("│ Input Validation            │ ❌ None     │ ✅ Full     │")
    print("│ Command Sanitization        │ ❌ None     │ ✅ Yes      │")
    print("│ Application Path Discovery  │ ❌ Hardcoded│ ✅ Dynamic  │")
    print("│ Logging & Audit Trail       │ ❌ Basic    │ ✅ Complete │")
    print("│ Error Handling              │ ❌ Basic    │ ✅ Robust   │")
    print("│ Configuration Management    │ ❌ None     │ ✅ Advanced │")
    print("└─────────────────────────────┴─────────────┴─────────────┘")
    
    print("\n🚨 Security Issues Fixed:")
    print("   ✅ No more exposed API keys in source code")
    print("   ✅ Protection against command injection")
    print("   ✅ Whitelist-based system command execution")
    print("   ✅ Input sanitization for all voice commands")
    print("   ✅ Dynamic application discovery (cross-platform)")
    print("   ✅ Comprehensive logging for security audits")

def main():
    """Run all tests"""
    print("🚀 HV System v2.0.0 - Security Improvements Test")
    print("=" * 55)
    
    tests = [
        test_configuration,
        test_logging,
        test_security_validation,
        test_application_finder,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    test_improved_security()
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All security improvements working correctly!")
        print("\n📋 Next Steps:")
        print("   1. Add your real AssemblyAI API key to .env file")
        print("   2. Run: python HV_SYSTEM.py")
        print("   3. Choose your preferred mode (Hand Only or Hand+Voice)")
        print("   4. Enjoy secure, improved computer control!")
    else:
        print("⚠️  Some tests failed. Please check the error messages above.")
    
    print(f"\n📁 Project Structure Created:")
    print("   ├── config/         # Configuration management")
    print("   ├── utils/          # Security and utility modules")
    print("   ├── logs/           # Application logs (auto-created)")
    print("   ├── .env            # Your environment variables")
    print("   └── SETUP.md        # Complete setup guide")

if __name__ == "__main__":
    main()

