export type SafeResult<T> = { data: T; ok: true } | { error: unknown; ok: false };

export const attempt = <T>(produce: () => T): SafeResult<T> => {
  try {
    return { data: produce(), ok: true };
  } catch (error) {
    return { error, ok: false };
  }
};

export const attemptAsync = async <T>(produce: () => Promise<T>): Promise<SafeResult<T>> => {
  try {
    return { data: await produce(), ok: true };
  } catch (error) {
    return { error, ok: false };
  }
};
