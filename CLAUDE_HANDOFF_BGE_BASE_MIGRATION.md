# Claude Handoff: BGE-Base Migration & Cleanup

## Current Situation

We attempted to upgrade from `bge-small-en-v1.5` to `gte-base-en-v1.5` (8192 context) but hit trust_remote_code interactive prompt issues that break nohup execution. We're now switching to `bge-base-en-v1.5` as a middle ground - better than small, no trust_remote_code hassle.

## What's Already Done

✅ `backend/config/search_config.py` - Updated to use bge-base-en-v1.5
✅ `deployment/scripts/download_model.sh` - Deleted (no longer needed)

## What Still Needs Cleanup

The following files may still have remnants of trust_remote_code or gte-base references that need to be verified and cleaned:

### 1. Systemd Service Files

**File**: `deployment/systemd/marxist-search-api.service`
- ✅ Should already have TRANSFORMERS_TRUST_REMOTE_CODE removed
- Verify lines 15-19 have NO mention of trust_remote_code

**File**: `deployment/systemd/marxist-search-update.service`
- ✅ Should already have TRANSFORMERS_TRUST_REMOTE_CODE removed
- Verify lines 14-17 have NO mention of trust_remote_code

### 2. Rebuild Scripts

**File**: `deployment/scripts/rebuild_all.sh`
- Check line ~273: Should be `sudo -u "$APP_USER" DATA_DIR="$DATA_DIR" ../venv/bin/python -m src.cli.marxist_cli index build`
- NO `TRANSFORMERS_TRUST_REMOTE_CODE=1` in the command

**File**: `deployment/scripts/rebuild_index.sh`
- Check line ~166: Should be `sudo -u "$APP_USER" DATA_DIR="$DATA_DIR" ../venv/bin/python -m src.cli.marxist_cli index build`
- NO `TRANSFORMERS_TRUST_REMOTE_CODE=1` in the command

### 3. Other Scripts to Check

**File**: `deployment/scripts/update_backend.sh`
- Verify no mention of download_model.sh or trust_remote_code

**File**: `deployment/scripts/update_frontend.sh`
- Should be fine, but verify no changes needed

**File**: `deployment/scripts/health_check.sh`
- Should be fine, verify no changes needed

### 4. Documentation Files

**File**: `deployment/DEPLOYMENT_GUIDE_v2.md`
- Verify it doesn't mention download_model.sh
- Verify it doesn't mention trust_remote_code
- Update any references to gte-base → bge-base

**File**: `README.md` (if it exists)
- Update model references if needed

## Target Configuration

### Model Settings

```python
# backend/config/search_config.py
TXTAI_CONFIG = {
    "path": "BAAI/bge-base-en-v1.5",  # NOT gte-base, NOT bge-small
    "content": False,
    "keyword": False,
    "backend": "numpy"
    # NO trust_remote_code parameter!
}
```

### Chunking Strategy for bge-base-en-v1.5

**Model specs**:
- Context window: 512 tokens
- ~1.33 tokens per word for English
- 512 tokens ≈ 384 words usable

**Optimal chunking** (currently set):
```python
CHUNKING_CONFIG = {
    "threshold_words": 350,    # Chunk if article > 350 words (~467 tokens)
    "chunk_size_words": 300,   # Each chunk ~300 words (~400 tokens)
    "overlap_words": 50,       # ~17% overlap for context continuity
    "prefer_section_breaks": True,
    "section_markers": ["##", "###", "\n\n"]
}
```

**Rationale**:
- 300-word chunks = ~400 tokens (leaves 112 token buffer)
- 50-word overlap ensures context continuity across chunk boundaries
- Most Marxist articles are essay-length, so chunking prevents truncation
- Section breaks preserve logical article structure

## Verification Checklist

Run these checks to ensure clean migration:

```bash
# 1. No trust_remote_code mentions anywhere
cd /home/user/marxist-search
grep -r "trust_remote_code" --include="*.py" --include="*.sh" --include="*.service" --include="*.md"
# Should return: NO RESULTS

# 2. No download_model.sh references
grep -r "download_model" --include="*.py" --include="*.sh" --include="*.service" --include="*.md"
# Should return: NO RESULTS

# 3. No gte-base references (should be bge-base)
grep -r "gte-base" --include="*.py" --include="*.sh" --include="*.service" --include="*.md"
# Should return: NO RESULTS

# 4. Confirm bge-base is set
grep -r "bge-base-en-v1.5" backend/config/search_config.py
# Should return: path: "BAAI/bge-base-en-v1.5"

# 5. Check git status
git status
# Should show: clean working tree OR only expected changes
```

## Commit and Push

Once everything is verified:

```bash
git add -A
git status  # Review changes
git commit -m "Complete migration to bge-base-en-v1.5 with optimized chunking

- Remove all trust_remote_code references from scripts and services
- Update chunking strategy for 512 token context window
- Clean documentation of gte-base references
- Verify bge-base-en-v1.5 loads without interactive prompts"

git push -u origin branch
```

## Expected Build Times

With bge-base-en-v1.5:
- Database rebuild: ~1-2 hours (if needed)
- Index build: ~3-5 hours
- **Total**: 4-7 hours (well under 8-hour requirement)

## Original Architecture (for reference)

Before the attempted gte upgrade, the system used:
- Model: `BAAI/bge-small-en-v1.5`
- No trust_remote_code complexity
- Simpler chunking (lower thresholds)
- All worked fine, just wanted better embeddings

We're keeping that clean architecture but upgrading to bge-base for better quality.

## Known Issues to Watch For

- **None** - bge-base-en-v1.5 is well-tested and widely used
- No trust_remote_code prompts
- Should work with txtai out of the box
- Chunking strategy is conservative and safe

## Success Criteria

✅ Config file uses `BAAI/bge-base-en-v1.5`
✅ No trust_remote_code anywhere in codebase
✅ No download_model.sh references
✅ Chunking configured for 512 token context
✅ All scripts run without interactive prompts
✅ Ready to rebuild index with nohup
