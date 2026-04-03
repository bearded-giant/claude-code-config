# Connecting Claude Code to Salesforce

This guide walks you through connecting Claude Code to your Salesforce org so Claude can query data, inspect metadata, run Apex tests, and manage users on your behalf.

The connection uses Salesforce's official MCP server: https://github.com/salesforcecli/mcp

> This integration is currently in **pilot/beta** from Salesforce.


## What You Need Before Starting

1. **Node.js** (version 18 or newer). Check by opening a terminal and running `node --version`. If you don't have it, download it from https://nodejs.org -- pick the LTS version.

2. **Salesforce CLI**. Check by running `sf --version` in a terminal. If you don't have it, install it by running:
   ```
   npm install -g @salesforce/cli
   ```

3. **A Salesforce org you can log into.** You'll need your username and password (or SSO access) for at least one Salesforce environment (production, sandbox, or dev org).


## Step 1: Log Into Your Salesforce Org

Open a terminal and run:

```
sf org login web --alias my-org --set-default
```

This opens a browser window. Log into the Salesforce org you want Claude to access. When it says "Authentication Successful", you can close the browser tab and go back to the terminal.

**What's happening:** This saves a secure token on your machine so the Salesforce tools can talk to your org without asking for your password every time. The `--alias my-org` part gives it a short name (you can change `my-org` to whatever you like). The `--set-default` part makes it the org that gets used automatically.

> If you use VS Code with the Salesforce Extension Pack, you may have already done this. You can check by running `sf org list` -- if you see your org listed, skip this step.


## Step 2: Add the Salesforce Server to Claude Code

You need to add a small block of configuration to Claude Code's settings file.

### Find your settings file

The file is at `~/.claude/settings.json`. To open it:

- **Mac:** Open Finder, press `Cmd + Shift + G`, type `~/.claude/settings.json`, and open it in any text editor.
- **Linux:** Open `~/.claude/settings.json` in your preferred editor.

### Add the configuration

Look for a section called `"mcpServers"` in the file. If it already exists, add the `"salesforce-dx"` block inside it. If it doesn't exist, add the entire `mcpServers` section. Place it after the last existing key, before the final closing `}`.

```json
"mcpServers": {
  "salesforce-dx": {
    "command": "npx",
    "args": [
      "-y",
      "@salesforce/mcp",
      "--orgs",
      "DEFAULT_TARGET_ORG",
      "--toolsets",
      "orgs,metadata,data,users",
      "--tools",
      "run_apex_test",
      "--allow-non-ga-tools"
    ]
  }
}
```

Make sure there's a comma after the line just before `"mcpServers"` -- JSON needs commas between sections.

### Alternative: Per-project setup

If you only want Salesforce available in a specific project (not everywhere), create a file called `.mcp.json` in that project's root folder with this content:

```json
{
  "mcpServers": {
    "salesforce-dx": {
      "command": "npx",
      "args": [
        "-y",
        "@salesforce/mcp",
        "--orgs",
        "DEFAULT_TARGET_ORG",
        "--toolsets",
        "orgs,metadata,data,users",
        "--tools",
        "run_apex_test",
        "--allow-non-ga-tools"
      ]
    }
  }
}
```

Save the file. That's it for config.


## Step 3: Restart Claude Code

Close and reopen Claude Code (or start a new session). The first time it loads the Salesforce server, it will download the package automatically -- this can take 10-20 seconds.


## Step 4: Approve Permissions

The first time Claude tries to use a Salesforce tool, it will ask for your permission. You'll see a prompt like:

```
Claude wants to use: mcp__salesforce-dx__query_records
Allow? (y/n)
```

Type `y` to approve. You'll only need to do this once per tool -- Claude remembers your choice.


## Verifying It Works

Start a Claude Code session and ask something like:

> "List my Salesforce orgs"

or

> "Query the first 5 Account records from Salesforce"

If Claude responds with real data from your org, everything is connected.


## What Can Claude Do With Salesforce?

The default config enables these tool groups:

| Group | What it does |
|-------|-------------|
| **orgs** | List connected orgs, check org status, view org details |
| **metadata** | Inspect custom objects, fields, Apex classes, triggers, flows |
| **data** | Run SOQL queries, create/update/delete records |
| **users** | List users, check profiles and permission sets |
| **run_apex_test** | Execute Apex test classes and return results |


## Connecting Additional Orgs

To add another org (like a sandbox), run:

```
sf org login web --alias my-sandbox
```

Then update the args in your config to expose multiple orgs. Replace:
```json
"--orgs",
"DEFAULT_TARGET_ORG",
```

With:
```json
"--orgs",
"DEFAULT_TARGET_ORG",
"--orgs",
"my-sandbox",
```

Or to let Claude access all orgs you've authenticated:
```json
"--orgs",
"ALLOW_ALL_ORGS",
```


## Troubleshooting

**"No default org set"**
You need to set a default org for the current project. Run `sf config set target-org my-org` (replacing `my-org` with your alias from Step 1).

**Claude says the Salesforce tools aren't available**
Make sure you saved the settings file and restarted Claude Code. Check that the JSON is valid -- a missing comma or bracket will break it. You can validate it at https://jsonlint.com.

**Login expired**
Salesforce tokens expire after a while. Re-run `sf org login web --alias my-org` to refresh.

**Slow first startup**
Normal. The first time, `npx` downloads the Salesforce MCP package. Subsequent starts are faster.

**Want to see what's happening under the hood?**
Add `"--debug"` to the args list (after `"--allow-non-ga-tools"`) and check the terminal output for detailed logs.
