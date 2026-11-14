import { Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { AppSettings, SettingsUpdate } from '../../models';
import { I18nService } from '../../i18n/i18n.service';
import { ApiService } from '../../services/api.service';
import { ChatService } from '../../services/chat.service';

@Component({
  selector: 'app-settings-panel',
  imports: [FormsModule],
  template: `
    <section class="settings">
      <header>
        <div>
          <h2>{{ i18n.t('settings.title') }}</h2>
          <p class="hint">{{ i18n.t('settings.hint') }}</p>
        </div>
        <button type="button" class="ghost" (click)="load()" [disabled]="loading || saving">
          {{ i18n.t('settings.reload') }}
        </button>
      </header>

      @if (loading) {
        <p class="hint">{{ i18n.t('settings.loading') }}</p>
      } @else {
        <fieldset>
          <legend>{{ i18n.t('settings.llm') }}</legend>
          <label class="field">
            <span>{{ i18n.t('settings.model') }}</span>
            <input
              [(ngModel)]="form.llm_model"
              name="llm_model"
              dir="ltr"
              [placeholder]="i18n.t('settings.providerModel')"
            />
          </label>
          <label class="field">
            <span>{{ i18n.t('settings.baseUrl') }}</span>
            <input
              [(ngModel)]="form.llm_base_url"
              name="llm_base_url"
              dir="ltr"
              [placeholder]="i18n.t('settings.providerDefault')"
            />
          </label>
          <label class="field">
            <span>
              {{ i18n.t('settings.apiKey') }}
              {{ flags.api_key_set ? i18n.t('settings.stored') : i18n.t('settings.notSet') }}
            </span>
            <input
              type="password"
              [(ngModel)]="form.llm_api_key"
              name="llm_api_key"
              autocomplete="off"
              dir="ltr"
              [disabled]="clear.llm_api_key"
              [placeholder]="
                flags.api_key_set
                  ? i18n.t('settings.apiKeyKeep')
                  : i18n.t('settings.apiKeyPlaceholder')
              "
            />
          </label>
          <label class="check">
            <input type="checkbox" [(ngModel)]="clear.llm_api_key" name="clear_llm" />
            {{ i18n.t('settings.clearApiKey') }}
          </label>
          <label class="field narrow">
            <span>{{ i18n.t('settings.temperature') }}</span>
            <input
              type="number"
              step="0.1"
              min="0"
              max="2"
              dir="ltr"
              [(ngModel)]="form.llm_temperature"
              name="llm_temperature"
            />
          </label>
          <div class="actions">
            <button type="button" class="ghost" (click)="testLlm()" [disabled]="testing !== ''">
              {{ testing === 'llm' ? i18n.t('settings.testing') : i18n.t('settings.testLlm') }}
            </button>
            @if (testTarget === 'llm' && testResult) {
              <span [class.ok]="testOk" [class.err]="!testOk">{{ testResult }}</span>
            }
          </div>
        </fieldset>

        <fieldset>
          <legend>{{ i18n.t('settings.nobitex') }}</legend>
          <label class="field narrow">
            <span>{{ i18n.t('settings.environment') }}</span>
            <select [(ngModel)]="form.nobitex_env" name="nobitex_env">
              <option value="mainnet">{{ i18n.t('settings.mainnet') }}</option>
              <option value="testnet">{{ i18n.t('settings.testnet') }}</option>
            </select>
          </label>
          <label class="field">
            <span>{{ i18n.t('settings.baseUrlOverride', { url: currentBaseUrl }) }}</span>
            <input
              [(ngModel)]="form.nobitex_base_url"
              name="nobitex_base_url"
              dir="ltr"
              [placeholder]="i18n.t('settings.baseUrlPlaceholder')"
            />
          </label>
          <label class="field narrow">
            <span>{{ i18n.t('settings.authMode') }}</span>
            <select [(ngModel)]="form.nobitex_auth_mode" name="nobitex_auth_mode">
              <option value="">{{ i18n.t('settings.autoDetect') }}</option>
              <option value="token">{{ i18n.t('settings.token') }}</option>
              <option value="key">{{ i18n.t('settings.ed25519') }}</option>
            </select>
          </label>
          <label class="field">
            <span>
              {{ i18n.t('settings.apiToken') }}
              {{ flags.token_set ? i18n.t('settings.stored') : i18n.t('settings.notSet') }}
            </span>
            <input
              type="password"
              [(ngModel)]="form.nobitex_token"
              name="nobitex_token"
              autocomplete="off"
              dir="ltr"
              [disabled]="clear.nobitex_token"
              [placeholder]="
                flags.token_set
                  ? i18n.t('settings.apiKeyKeep')
                  : i18n.t('settings.nobitexTokenPlaceholder')
              "
            />
          </label>
          <label class="check">
            <input type="checkbox" [(ngModel)]="clear.nobitex_token" name="clear_token" />
            {{ i18n.t('settings.clearToken') }}
          </label>
          <label class="field">
            <span>
              {{ i18n.t('settings.publicKey') }}
              {{ flags.public_key_set ? i18n.t('settings.stored') : i18n.t('settings.notSet') }}
            </span>
            <input
              type="password"
              [(ngModel)]="form.nobitex_public_key"
              name="nobitex_public_key"
              autocomplete="off"
              dir="ltr"
              [disabled]="clear.nobitex_public_key"
            />
          </label>
          <label class="check">
            <input type="checkbox" [(ngModel)]="clear.nobitex_public_key" name="clear_public" />
            {{ i18n.t('settings.clearPublicKey') }}
          </label>
          <label class="field">
            <span>
              {{ i18n.t('settings.privateKey') }}
              {{ flags.private_key_set ? i18n.t('settings.stored') : i18n.t('settings.notSet') }}
            </span>
            <input
              type="password"
              [(ngModel)]="form.nobitex_private_key"
              name="nobitex_private_key"
              autocomplete="off"
              dir="ltr"
              [disabled]="clear.nobitex_private_key"
            />
          </label>
          <label class="check">
            <input type="checkbox" [(ngModel)]="clear.nobitex_private_key" name="clear_private" />
            {{ i18n.t('settings.clearPrivateKey') }}
          </label>
          <label class="check">
            <input type="checkbox" [(ngModel)]="form.nobitex_dry_run" name="dry_run" />
            {{ i18n.t('settings.paperTrading') }}
          </label>
          <label class="check">
            <input type="checkbox" [(ngModel)]="form.nobitex_read_only" name="read_only" />
            {{ i18n.t('settings.readOnly') }}
          </label>
          <div class="actions">
            <button type="button" class="ghost" (click)="testNobitex()" [disabled]="testing !== ''">
              {{ testing === 'nobitex' ? i18n.t('settings.testing') : i18n.t('settings.testNobitex') }}
            </button>
            @if (testTarget === 'nobitex' && testResult) {
              <span [class.ok]="testOk" [class.err]="!testOk">{{ testResult }}</span>
            }
          </div>
        </fieldset>

        <fieldset>
          <legend>{{ i18n.t('settings.agentScheduler') }}</legend>
          <label class="field narrow">
            <span>{{ i18n.t('settings.maxIterations') }}</span>
            <input
              type="number"
              min="1"
              max="500"
              dir="ltr"
              [(ngModel)]="form.agent_max_iterations"
              name="agent_max_iterations"
            />
          </label>
          <label class="field narrow">
            <span>{{ i18n.t('settings.schedulerTimezone') }}</span>
            <input [(ngModel)]="form.scheduler_timezone" name="scheduler_timezone" dir="ltr" />
          </label>
          <label class="check">
            <input type="checkbox" [(ngModel)]="form.scheduler_enabled" name="scheduler_enabled" />
            {{ i18n.t('settings.enableScheduler') }}
          </label>
          <label class="check danger">
            <input type="checkbox" [(ngModel)]="form.allow_withdrawals" name="allow_withdrawals" />
            {{ i18n.t('settings.allowWithdrawals') }}
          </label>
        </fieldset>

        <div class="actions">
          <button type="button" class="primary" (click)="save()" [disabled]="saving">
            {{ saving ? i18n.t('settings.saving') : i18n.t('settings.save') }}
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
  readonly i18n = inject(I18nService);

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
      this.message = this.i18n.t('settings.saved');
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
      return detail
        .map((item) => (item as { msg?: string })?.msg ?? this.i18n.t('settings.invalidValue'))
        .join('; ');
    }
    return failure?.message ?? this.i18n.t('settings.requestFailed');
  }
}
