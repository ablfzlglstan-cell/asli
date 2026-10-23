# VynexaVPN Bot

## Files
- `VynexaVPN_REBUILT_LATEST.py`: main bot script (upload separately).
- `requirements.txt`: Python packages (verify against imports in the main script).
- `Procfile`: worker start command for hosts that support Procfile.
- `runtime.txt`: requested Python runtime for buildpacks that support this file.
- `.env.example`: placeholder only; never add real tokens or passwords to GitHub.
- `.gitignore`: avoids committing common secrets and runtime files.

## Deploy
1. Upload these files plus `VynexaVPN_REBUILT_LATEST.py` to the same repository root.
2. Configure secrets/environment variables in the hosting provider's dashboard, not in GitHub.
3. Set the worker start command to:
   `python VynexaVPN_REBUILT_LATEST.py`
4. Check the host logs after deployment.

Important: `requirements.txt` is a starter list, not yet verified against the script's imports. The script may need additional packages or different versions. Some hosting platforms require a different start command or configuration.
