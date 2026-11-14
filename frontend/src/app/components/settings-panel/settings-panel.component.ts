import { Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { AppSettings, SettingsUpdate } from '../../models';
import { ApiService } from '../../services/api.service';
import { ChatService } from '../../services/chat.service';

@Component({
  selector: 'app-settings-panel',
  imports: [FormsModule],
  template: `
    <section class="settings">
      <header>
        <div>
          <h2>Configuration</h2>
          <p class="hint">Saved to <code>.env</code>. New chat sessions pick up changes.</p>
        </div>
        <button type="button" class="ghost" (click)="load()" [disabled]="loading || saving">
          Reload
        </button>
      </header>

      @if (loading) {
        <p class="hint">Loading configuration…</p>
      } @else {
        <fieldset>
          <legend>LLM</legend>
          <label class="field">
            <span>Model</span>
            <input [(ngModel)]="form.llm_model" name="llm_model" placeholder="provider/model" />
          </label>
          <label class="field">
            <span>Base URL</span>
            <input
              [(ngModel)]="form.llm_base_url"
              name="llm_base_url"
              placeholder="provider default"
            />
          </label>
          <label class="field">
            <span>API key {{ flags.api_key_set ? '(stored)' : '(not set)' }}</span>
            <input
              type="password"
              [(ngModel)]="form.llm_api_key"
              name="llm_api_key"
              autocomplete="off"
              [disabled]="clear.llm_api_key"
              [placeholder]="flags.api_key_set ? '•••••••• leave blank to keep' : 'sk-…'"
            />
          </label>
          <label class="check">
            <input type="checkbox" [(ngModel)]="clear.llm_api_key" name="clear_llm" />
            Clear stored API key
          </label>
          <label class="field narrow">
            <span>Temperature</span>
            <input
              type="number"
              step="0.1"
              min="0"
              max="2"
              [(ngModel)]="form.llm_temperature"
              name="llm_temperature"
            />
          </label>
          <div class="actions">
            <button type="button" class="ghost" (click)="testLlm()" [disabled]="testing !== ''">
              {{ testing === 'llm' ? 'Testing…' : 'Test LLM' }}
            </button>
            @if (testTarget === 'llm' && testResult) {
              <span [class.ok]="testOk" [class.err]="!testOk">{{ testResult }}</span>
            }
          </div>
        </fieldset>

        <fieldset>
          <legend>Nobitex</legend>
          <label class="field narrow">
            <span>Environment</span>
            <select [(ngModel)]="form.nobitex_env" name="nobitex_env">
              <option value="mainnet">mainnet</option>
              <option value="testnet">testnet</option>
            </select>
          </label>
          <label class="field">
            <span>Base URL override ({{ currentBaseUrl }})</span>
            <input
              [(ngModel)]="form.nobitex_base_url"
              name="nobitex_base_url"
              placeholder="leave blank for the environment default"
            />
          </label>
          <label class="field narrow">
            <span>Auth mode</span>
            <select [(ngModel)]="form.nobitex_auth_mode" name="nobitex_auth_mode">
              <option value="">auto-detect</option>
              <option value="token">token</option>
              <option value="key">Ed25519 key</option>
            </select>
          </label>
          <label class="field">
            <span>API token {{ flags.token_set ? '(stored)' : '(not set)' }}</span>
            <input
              type="password"
              [(ngModel)]="form.nobitex_token"
              name="nobitex_token"
              autocomplete="off"
              [disabled]="clear.nobitex_token"
              [placeholder]="flags.token_set ? '•••••••• leave blank to keep' : 'Nobitex API token'"
            />
          </label>
          <label class="check">
            <input type="checkbox" [(ngModel)]="clear.nobitex_token" name="clear_token" />
            Clear stored token
          </label>
          <label class="field">
            <span>Ed25519 public key {{ flags.public_key_set ? '(stored)' : '(not set)' }}</span>
            <input
              type="password"
              [(ngModel)]="form.nobitex_public_key"
              name="nobitex_public_key"
              autocomplete="off"
              [disabled]="clear.nobitex_public_key"
            />
          </label>
          <label class="check">
            <input type="checkbox" [(ngModel)]="clear.nobitex_public_key" name="clear_public" />
            Clear stored public key
          </label>
          <label class="field">
            <span>Ed25519 private key {{ flags.private_key_set ? '(stored)' : '(not set)' }}</span>
            <input
              type="password"
              [(ngModel)]="form.nobitex_private_key"
              name="nobitex_private_key"
              autocomplete="off"
              [disabled]="clear.nobitex_private_key"
            />
          </label>
          <label class="check">
            <input type="checkbox" [(ngModel)]="clear.nobitex_private_key" name="clear_private" />
            Clear stored private key
          </label>
          <label class="check">
            <input type="checkbox" [(ngModel)]="form.nobitex_dry_run" name="dry_run" />
            Paper trading (dry run)
          </label>
          <label class="check">
            <input type="checkbox" [(ngModel)]="form.nobitex_read_only" name="read_only" />
            Read-only (block all orders)
          </label>
          <div class="actions">
            <button type="button" class="ghost" (click)="testNobitex()" [disabled]="testing !== ''">
              {{ testing === 'nobitex' ? 'Testing…' : 'Test Nobitex' }}
            </button>
            @if (testTarget === 'nobitex' && testResult) {
              <span [class.ok]="testOk" [class.err]="!testOk">{{ testResult }}</span>
            }
          </div>
        </fieldset>

        <fieldset>
          <legend>Agent &amp; scheduler</legend>
          <label class="field narrow">
            <span>Max iterations</span>
            <input
              type="number"
              min="1"
              max="500"
              [(ngModel)]="form.agent_max_iterations"
              name="agent_max_iterations"
            />
          </label>
          <label class="field narrow">
            <span>Scheduler timezone</span>
            <input [(ngModel)]="form.scheduler_timezone" name="scheduler_timezone" />
          </label>
          <label class="check">
            <input type="checkbox" [(ngModel)]="form.scheduler_enabled" name="scheduler_enabled" />
            Enable scheduled tasks
          </label>
          <label class="check danger">
            <input type="checkbox" [(ngModel)]="form.allow_withdrawals" name="allow_withdrawals" />
            Allow withdrawal and credential tools (dangerous)
          </label>
        </fieldset>

        <div class="actions">
          <button type="button" class="primary" (click)="save()" [disabled]="saving">
            {{ saving ? 'Saving…' : 'Save configuration' }}
          </button>
          @if (message) {
            <span class="ok">{{ message }}</span>
          }
          @if (error) {
            <span class="err">{{ error }}</span>
          }
        </div>
      }
    </section>
  `,
  styles: [
    `
      :host {
        display: block;
      }
      .settings {
        display: flex;
        flex-direction: column;
        gap: 12px;
      }
      header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 8px;
      }
      h2 {
        margin: 0;
        font-size: 15px;
      }
      .hint {
        margin: 2px 0 0;
        font-size: 11px;
        color: #64748b;
      }
      code {
        color: #94a3b8;
      }
      fieldset {
        border: 1px solid #1e293b;
        border-radius: 10px;
        padding: 10px 12px 12px;
        display: flex;
        flex-direction: column;
        gap: 8px;
        margin: 0;
      }
      legend {
        padding: 0 6px;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #38bdf8;
      }
      .field {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }
      .field.narrow {
        max-width: 220px;
      }
      .field span {
        font-size: 11px;
        color: #94a3b8;
      }
      input,
      select {
        background: #0b1220;
        border: 1px solid #1e293b;
        border-radius: 8px;
        color: #e2e8f0;
        padding: 7px 9px;
        font-family: inherit;
        font-size: 12.5px;
      }
      input:focus,
      select:focus {
        outline: none;
        border-color: #38bdf8;
      }
      input:disabled {
        opacity: 0.5;
      }
      .check {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 12px;
        color: #cbd5e1;
      }
      .check input {
        width: 14px;
        height: 14px;
        accent-color: #0284c7;
      }
      .check.danger {
        color: #fca5a5;
      }
      .actions {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 10px;
      }
      button {
        border-radius: 8px;
        padding: 8px 14px;
        font-weight: 600;
        font-size: 12px;
        cursor: pointer;
        border: 1px solid #1e293b;
        background: #111c2e;
        color: #cbd5e1;
      }
      button.primary {
        background: #0284c7;
        border-color: #0284c7;
        color: white;
      }
      button:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
      .ok {
        font-size: 11px;
        color: #4ade80;
      }
      .err {
        font-size: 11px;
        color: #fca5a5;
      }
    `,
  ],
})
export class SettingsPanelComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly chat = inject(ChatService);

  loading = true;
  saving = false;
  testing = '';
  testTarget = '';
  testResult = '';
  testOk = false;
  message = '';
  error = '';
  currentBaseUrl = '';

  flags = {
    api_key_set: false,
    token_set: false,
    public_key_set: false,
    private_key_set: false,
  };

  clear = {
    llm_api_key: false,
    nobitex_token: false,
    nobitex_public_key: false,
    nobitex_private_key: false,
  };

  form = {
    llm_model: '',
    llm_api_key: '',
    llm_base_url: '',
    llm_temperature: 0.2,
    nobitex_env: 'mainnet',
    nobitex_base_url: '',
    nobitex_token: '',
    nobitex_public_key: '',
    nobitex_private_key: '',
    nobitex_auth_mode: '',
    nobitex_dry_run: true,
    nobitex_read_only: false,
    allow_withdrawals: false,
    agent_max_iterations: 60,
    scheduler_enabled: true,
    scheduler_timezone: 'Asia/Tehran',
  };

  async ngOnInit(): Promise<void> {
    await this.load();
  }

  async load(): Promise<void> {
    this.loading = true;
    this.error = '';
    try {
      this.apply(await firstValueFrom(this.api.settings()));
    } catch (err) {
      this.error = this.describe(err);
    } finally {
      this.loading = false;
    }
  }

  async save(): Promise<void> {
    this.saving = true;
    this.message = '';
    this.error = '';
    try {
      const updated = await firstValueFrom(this.api.updateSettings(this.payload()));
      this.apply(updated);
      this.chat.reset();
      this.message = 'Saved. New chat sessions use this configuration.';
    } catch (err) {
      this.error = this.describe(err);
    } finally {
      this.saving = false;
    }
  }

  async testLlm(): Promise<void> {
    await this.runTest('llm');
  }

  async testNobitex(): Promise<void> {
    await this.runTest('nobitex');
  }

  private async runTest(target: 'llm' | 'nobitex'): Promise<void> {
    this.testing = target;
    this.testTarget = target;
    this.testResult = '';
    try {
      const result = await firstValueFrom(
        target === 'llm' ? this.api.testLlm() : this.api.testNobitex(),
      );
      this.testOk = result.ok;
      this.testResult = result.detail;
    } catch (err) {
      this.testOk = false;
      this.testResult = this.describe(err);
    } finally {
      this.testing = '';
    }
  }

  private payload(): SettingsUpdate {
    const payload: SettingsUpdate = {
      llm_model: this.form.llm_model.trim(),
      llm_base_url: this.form.llm_base_url.trim() || null,
      llm_temperature: Number(this.form.llm_temperature),
      nobitex_env: this.form.nobitex_env === 'testnet' ? 'testnet' : 'mainnet',
      nobitex_base_url: this.form.nobitex_base_url.trim() || null,
      nobitex_auth_mode:
        this.form.nobitex_auth_mode === 'token' || this.form.nobitex_auth_mode === 'key'
          ? this.form.nobitex_auth_mode
          : null,
      nobitex_dry_run: this.form.nobitex_dry_run,
      nobitex_read_only: this.form.nobitex_read_only,
      allow_withdrawals: this.form.allow_withdrawals,
      agent_max_iterations: Number(this.form.agent_max_iterations),
      scheduler_enabled: this.form.scheduler_enabled,
      scheduler_timezone: this.form.scheduler_timezone.trim(),
    };
    this.secret(payload, 'llm_api_key', this.form.llm_api_key, this.clear.llm_api_key);
    this.secret(payload, 'nobitex_token', this.form.nobitex_token, this.clear.nobitex_token);
    this.secret(
      payload,
      'nobitex_public_key',
      this.form.nobitex_public_key,
      this.clear.nobitex_public_key,
    );
    this.secret(
      payload,
      'nobitex_private_key',
      this.form.nobitex_private_key,
      this.clear.nobitex_private_key,
    );
    return payload;
  }

  private secret(
    payload: SettingsUpdate,
    key: 'llm_api_key' | 'nobitex_token' | 'nobitex_public_key' | 'nobitex_private_key',
    value: string,
    clear: boolean,
  ): void {
    if (clear) {
      payload[key] = '';
    } else if (value.trim()) {
      payload[key] = value.trim();
    }
  }

  private apply(settings: AppSettings): void {
    this.form.llm_model = settings.llm.model;
    this.form.llm_base_url = settings.llm.base_url ?? '';
    this.form.llm_temperature = settings.llm.temperature;
    this.form.nobitex_env = settings.nobitex.env;
    this.form.nobitex_base_url = settings.nobitex.base_url_override ?? '';
    this.form.nobitex_auth_mode = settings.nobitex.auth_mode ?? '';
    this.form.nobitex_dry_run = settings.nobitex.dry_run;
    this.form.nobitex_read_only = settings.nobitex.read_only;
    this.form.agent_max_iterations = settings.agent.max_iterations;
    this.form.allow_withdrawals = settings.agent.allow_withdrawals;
    this.form.scheduler_enabled = settings.scheduler.enabled;
    this.form.scheduler_timezone = settings.scheduler.timezone;
    this.currentBaseUrl = settings.nobitex.base_url;

    this.flags = {
      api_key_set: settings.llm.api_key_set,
      token_set: settings.nobitex.token_set,
      public_key_set: settings.nobitex.public_key_set,
      private_key_set: settings.nobitex.private_key_set,
    };
    this.form.llm_api_key = '';
    this.form.nobitex_token = '';
    this.form.nobitex_public_key = '';
    this.form.nobitex_private_key = '';
    this.clear = {
      llm_api_key: false,
      nobitex_token: false,
      nobitex_public_key: false,
      nobitex_private_key: false,
    };
  }

  private describe(err: unknown): string {
    const failure = err as { error?: { detail?: unknown }; message?: string };
    const detail = failure?.error?.detail;
    if (typeof detail === 'string') {
      return detail;
    }
    if (Array.isArray(detail)) {
      return detail.map((item) => (item as { msg?: string })?.msg ?? 'invalid value').join('; ');
    }
    return failure?.message ?? 'Request failed';
  }
}
