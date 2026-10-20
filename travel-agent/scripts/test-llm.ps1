$ErrorActionPreference = 'Stop'
$agentEnvPath = Join-Path (Split-Path -Parent $PSScriptRoot) '.env'
$agentSettings = @{}
Get-Content -LiteralPath $agentEnvPath -Encoding UTF8 | ForEach-Object {
    if ($_ -match '^\s*([^#=\s]+)\s*=(.*)$') {
        $agentSettings[$matches[1]] = $matches[2].Trim().Trim('"').Trim("'")
    }
}
foreach ($agentRequired in @('LLM_MODEL', 'LLM_BASE_URL', 'LLM_API_KEY')) {
    if (-not $agentSettings[$agentRequired]) { throw "Missing setting: $agentRequired" }
}
$agentHeaders = @{ Authorization = 'Bearer ' + $agentSettings['LLM_API_KEY'] }
$agentEndpoint = $agentSettings['LLM_BASE_URL'].TrimEnd('/') + '/chat/completions'
$agentPrompt = @{role='user'; content='Call connection_check with value ping.'}
$agentPayload = @{
    model = $agentSettings['LLM_MODEL']
    messages = @($agentPrompt)
    tools = @(@{type='function'; function=@{
        name='connection_check'
        description='Check tool calling connectivity'
        parameters=@{type='object'; properties=@{value=@{type='string'}}; required=@('value'); additionalProperties=$false}
    }})
    tool_choice = @{type='function'; function=@{name='connection_check'}}
    max_tokens = 128
}
try {
    $agentResponse = Invoke-RestMethod -Method Post -Uri $agentEndpoint -Headers $agentHeaders -ContentType 'application/json' -Body ($agentPayload | ConvertTo-Json -Depth 15 -Compress) -TimeoutSec 35
    $agentMessage = $agentResponse.choices[0].message
    $agentCalls = @($agentMessage.tool_calls)
    if ($agentCalls.Count -ne 1 -or $agentCalls[0].function.name -ne 'connection_check') {
        throw 'The model did not return the requested tool call.'
    }
    $agentArguments = $agentCalls[0].function.arguments | ConvertFrom-Json
    if ($agentArguments.value -ne 'ping') { throw 'Unexpected tool arguments.' }
    Write-Output 'PASS: API authentication and native tool calling'
    Write-Output ('Returned model: ' + $agentResponse.model)
    $agentFollowup = @{
        model=$agentSettings['LLM_MODEL']
        messages=@($agentPrompt, $agentMessage, @{role='tool'; tool_call_id=$agentCalls[0].id; content='{"status":"ok"}'}, @{role='user'; content='Reply only CONNECTION_OK.'})
        max_tokens=64
    }
    $agentFinal = Invoke-RestMethod -Method Post -Uri $agentEndpoint -Headers $agentHeaders -ContentType 'application/json' -Body ($agentFollowup | ConvertTo-Json -Depth 15 -Compress) -TimeoutSec 35
    if ($agentFinal.choices[0].message.content.Trim() -ne 'CONNECTION_OK') {
        throw 'The model responded, but the final confirmation was unexpected.'
    }
    Write-Output 'PASS: Tool-result round trip (CONNECTION_OK)'
    Write-Output 'Model connectivity passed. Java business integration is a separate check.'
} catch {
    Write-Output ('FAIL: ' + $_.Exception.GetType().Name)
    if ($_.Exception.Response) {
        Write-Output ('HTTP status: ' + [int]$_.Exception.Response.StatusCode)
    }
    # Do not print request headers, API keys, or raw provider error responses.
    exit 1
}
