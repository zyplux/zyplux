export const ensure: (isMet: boolean, message: string) => asserts isMet = (isMet, message) => {
  if (!isMet) {
    throw new Error(message);
  }
};
