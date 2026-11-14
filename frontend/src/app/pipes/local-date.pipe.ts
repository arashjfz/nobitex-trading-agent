import { Pipe, PipeTransform } from '@angular/core';

@Pipe({ name: 'localDate', standalone: true })
export class LocalDatePipe implements PipeTransform {
  transform(
    value: string | number | Date | null | undefined,
    locale: string,
    mode: 'short' | 'time' = 'short',
  ): string {
    if (value === null || value === undefined || value === '') {
      return '';
    }
    const date = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(date.getTime())) {
      return String(value);
    }
    const options: Intl.DateTimeFormatOptions =
      mode === 'time'
        ? { hour: '2-digit', minute: '2-digit' }
        : { dateStyle: 'short', timeStyle: 'short' };
    return new Intl.DateTimeFormat(locale, options).format(date);
  }
}
