"""job-pipeline — shared package for the job-search pipeline.

Public surface:
    from jobpipeline import config        — load profile/scoring/geo YAML
    from jobpipeline.db import connect    — SQLite connection helper
    from jobpipeline.models import ...    — Posting, Application, SourceRun
    from jobpipeline.persistence import ... — upsert + status helpers
    from jobpipeline.achievements import ... — streak / weekly / funnel / picks
    from jobpipeline.jokes import ...     — pick-me-up jokes + mascot quotes
    from jobpipeline.geo import ...       — geo tier detection
"""
