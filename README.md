# TUSOME School Management System

A comprehensive web-based school management system built with Flask, designed for managing students, grades, fees, and parent communication.

## Features

### 👨‍💼 Admin Dashboard
- Student enrollment management
- Grade entry and management
- Fee structure setup
- Parent account management
- School announcements
- Comprehensive reporting

### 👨‍👩‍👧‍👦 Parent Portal
- View children's academic performance
- Track fee payments and balances
- Receive school announcements
- Download reports and statements
- Real-time grade updates

### 📊 Academic Management
- Subject-wise grade tracking
- Term-based performance analysis
- Grade point calculation
- Performance visualization
- Progress tracking

### 💰 Fee Management
- Multiple fee types support
- Payment tracking
- Balance calculations
- Overdue notifications
- Payment history

## Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/tusome-school-system.git
cd tusome-school-system
python -m venv venv
source venv/bin/activate  # On Windows: .venv/Scripts/activate
Install dependencies
bash


pip install -r requirements.txt
Run the application
bash


python app.py


# Clone the repository
git clone https://github.com/douglaskiplagatc-hue/tusome-academy
cd tusome-academy

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install depen

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Initialize database
python -c "from app import app, db; app.app_context().push(); db.create_all()"

# Create admin user
python create_admin.py

# Run the application
python app.py

#Production Deployment
# Using Docker
docker-compose up -d

# Or using traditional deployment
pip install -r requirements.txt
gunicorn --bind 0.0.0.0:5000 --workers 4 app:app

flask db init
flask db migrate -m "describe the change here"
flask db upgrade
flask db downgrade
SurfaceFlinger
  accessibility
  account
  activity
  activity_task
  alarm
  android.security.identity
  android.security.keystore
  android.service.gatekeeper.IGateKeeperService
  anrmanager
  appops
  appwidget
  audio
  auth
  autofill
  backup
  batteryproperties
  batterystats
  biometric
  blob_store
  bluetooth_manager
  capctrl
  carrier_config
  clipboard
  companiondevice
  connectivity
  connmetrics
  consumer_ir
  content
  country_detector
  crossprofileapps
  device_identifiers
  device_policy
  deviceidle
  display
  dreams
  drm.drmManager
  dropbox
  file_integrity
  fingerprint
  gpu
  graphicsstats
  hardware_properties
  imms
  imtksms
  input
  input_method
  ions
  iphonesubinfo
  iphonesubinfoEx
  ipsec
  isms
  isub
  isubstub
  jobscheduler
  kolun
  launcherapps
  lights
  location
  media.audio_flinger
  media.audio_policy
  media.camera
  media.extractor
  media.metrics
  media.player
  media.resource_manager
  media_projection
  media_resource_monitor
  media_router
  media_session
  midi
  mount
  mtkIms
  mtk_telecom
  mtksimphonebook
  mwis
  netpolicy
  netstats
  network_management
  notification
  package
  package_native
  permission
  permissionmgr
  phone
  phoneEx
  platform_compat
  platform_compat_native
  power
  power_hal_mgr_service
  print
  procstats
  restrictions
  role
  rollback
  sand_accessor
  search
  search_engine_service
  sec_key_att_app_id_provider
  sensor_privacy
  sensorservice
  servicediscovery
  settings
  shortcut
  simphonebook
  slice
  soundtrigger
  statusbar
  storagestats
  telecom
  telephony.mtkregistry
  telephony.registry
  telephony_ims
  tethering
  textclassification
  textservices
  thermalservice
  tran_pwhub
  tran_tranlog
  tranlog_sub
  trust
  uimode
  uri_grants
  usagestats
  usb
  user
  uxdetectorrest
  vibrator
  voiceinteraction
  vow_bridge
  wallpaper
  webviewupdate
  wifi
  wifip2p


python
from app import app          # your Flask app object
from extensions import db

with app.app_context():
    db.create_all()
djlint . --reformat

# how about formatting scripts and styles?
djlint . --reformat --format-css --format-js

from app import app
from extensions import db
from models import SalaryPaymentExecution,Bursary,Scholarship

with app.app_context():
    db.create_all()