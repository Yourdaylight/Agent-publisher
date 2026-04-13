declare module 'qrcode' {
  interface QRCodeToDataURLOptions {
    width?: number;
    margin?: number;
    color?: {
      dark?: string;
      light?: string;
    };
    errorCorrectionLevel?: string;
  }

  export function toDataURL(
    text: string,
    options?: QRCodeToDataURLOptions,
  ): Promise<string>;

  export function toDataURL(
    text: string,
    cb: (err: Error | null | undefined, url: string) => void,
  ): void;

  export function toDataURL(
    text: string,
    options: QRCodeToDataURLOptions,
    cb: (err: Error | null | undefined, url: string) => void,
  ): void;
}
