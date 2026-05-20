@{
    # Invoke-ScriptAnalyzer auto-loads this file when it sits in the -Path root.
    # Rules excluded below are noise for this repo's lone PowerShell entry
    # point (scripts/build-release.ps1), which intentionally:
    #   - Uses Write-Host for colorized user-facing build output (no pipeline)
    #   - Calls cmdlets positionally where the intent is unambiguous
    # Re-enable by deleting the rule from this list and fixing the script.
    ExcludeRules = @(
        'PSAvoidUsingWriteHost',
        'PSAvoidUsingPositionalParameters',
        'PSUseBOMForUnicodeEncodedFile'
    )
}
