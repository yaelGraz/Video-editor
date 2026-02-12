import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
Config.setJpegQuality(80);
Config.setConcurrency(0); // 0 = auto (use all cores)
