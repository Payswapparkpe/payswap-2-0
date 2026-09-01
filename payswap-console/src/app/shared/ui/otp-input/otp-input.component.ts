import { Component, ElementRef, forwardRef, QueryList, ViewChildren } from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';

@Component({
  selector: 'app-otp-input',
  standalone: true,
  template: `
    <div class="otp" role="group" aria-label="One-time password">
      @for (digit of digits; track $index) {
        <input
          #box
          class="otp-box"
          maxlength="1"
          inputmode="numeric"
          autocomplete="one-time-code"
          [value]="digit"
          (input)="onInput($event, $index)"
          (keydown)="onKey($event, $index)"
          (paste)="onPaste($event)"
        />
      }
    </div>
  `,
  styles: [
    `
      .otp {
        display: flex;
        gap: 10px;
      }
      .otp-box {
        width: 48px;
        height: 56px;
        text-align: center;
        font-size: 22px;
        font-weight: 700;
        border-radius: 12px;
        border: 1px solid #d9d3e8;
        background: #fff;
        color: #13101c;
      }
      .otp-box:focus {
        outline: 2px solid #1b4dfe;
        outline-offset: 1px;
      }
    `,
  ],
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => OtpInputComponent),
      multi: true,
    },
  ],
})
export class OtpInputComponent implements ControlValueAccessor {
  digits = ['', '', '', '', '', ''];
  @ViewChildren('box') boxes!: QueryList<ElementRef<HTMLInputElement>>;

  private onChange: (value: string) => void = () => undefined;
  private onTouched: () => void = () => undefined;

  writeValue(value: string | null): void {
    const chars = (value ?? '').slice(0, 6).split('');
    this.digits = Array.from({ length: 6 }, (_, i) => chars[i] ?? '');
  }

  registerOnChange(fn: (value: string) => void): void {
    this.onChange = fn;
  }

  registerOnTouched(fn: () => void): void {
    this.onTouched = fn;
  }

  onInput(event: Event, index: number): void {
    const input = event.target as HTMLInputElement;
    const char = input.value.replace(/\D/g, '').slice(-1);
    this.digits[index] = char;
    input.value = char;
    this.emit();
    if (char && index < 5) {
      this.boxes.get(index + 1)?.nativeElement.focus();
    }
  }

  onKey(event: KeyboardEvent, index: number): void {
    if (event.key === 'Backspace' && !this.digits[index] && index > 0) {
      this.boxes.get(index - 1)?.nativeElement.focus();
    }
  }

  onPaste(event: ClipboardEvent): void {
    event.preventDefault();
    const text = event.clipboardData?.getData('text') ?? '';
    const chars = text.replace(/\D/g, '').slice(0, 6).split('');
    this.digits = Array.from({ length: 6 }, (_, i) => chars[i] ?? '');
    this.emit();
    const focusAt = Math.min(chars.length, 5);
    this.boxes.get(focusAt)?.nativeElement.focus();
  }

  private emit(): void {
    this.onTouched();
    this.onChange(this.digits.join(''));
  }
}
