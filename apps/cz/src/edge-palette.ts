const EDGE_HUE_START_DEG = 210;
const FULL_HUE_TURN_DEG = 360;
const EDGE_COLOR_SATURATION = 0.7;
const EDGE_COLOR_LIGHTNESS = 0.65;
const HUE_TO_SECTOR_DIVISOR = 30;
const SECTOR_WRAP = 12;
const SECTOR_PEAK_START = 3;
const SECTOR_PEAK_END = 9;
const RED_CHANNEL_OFFSET = 0;
const GREEN_CHANNEL_OFFSET = 8;
const BLUE_CHANNEL_OFFSET = 4;
const RGB_MAX = 255;
const HEX_BASE = 16;
const HEX_BYTE_LENGTH = 2;

type HslColor = { hue: number; lightness: number; saturation: number };

const calcRgbChannel = ({ hue, lightness, saturation }: HslColor, channelOffset: number) => {
  const sector = (channelOffset + hue / HUE_TO_SECTOR_DIVISOR) % SECTOR_WRAP;
  const amplitude = saturation * Math.min(lightness, 1 - lightness);
  return lightness - amplitude * Math.max(-1, Math.min(sector - SECTOR_PEAK_START, SECTOR_PEAK_END - sector, 1));
};

const toHexByte = (unitValue: number) =>
  Math.round(unitValue * RGB_MAX)
    .toString(HEX_BASE)
    .padStart(HEX_BYTE_LENGTH, '0');

const formatHslAsHex = (color: HslColor) => {
  const channelOffsets = [RED_CHANNEL_OFFSET, GREEN_CHANNEL_OFFSET, BLUE_CHANNEL_OFFSET];
  return `#${channelOffsets.map(channelOffset => toHexByte(calcRgbChannel(color, channelOffset))).join('')}`;
};

export const calcEdgeColor = (edgeSourceIndex: number, edgeSourceCount: number) => {
  const hue = (EDGE_HUE_START_DEG + (edgeSourceIndex * FULL_HUE_TURN_DEG) / edgeSourceCount) % FULL_HUE_TURN_DEG;
  return formatHslAsHex({ hue, lightness: EDGE_COLOR_LIGHTNESS, saturation: EDGE_COLOR_SATURATION });
};
