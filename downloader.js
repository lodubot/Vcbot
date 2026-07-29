const fs = require('fs-extra');
const path = require('path');
const axios = require('axios');
const yts = require('yt-search');
const config = require('./config.js');
const db = require('./db.js');

fs.ensureDirSync(config.cacheDir);

async function fetchDownloadUrl(youtubeUrl, isVideo = false) {
    const format = isVideo ? 'mp4' : 'mp3';

    // 1. Primary Scraper: Y2Mate
    try {
        const y2mateModule = require('./y2matre.js');
        const res = await y2mateModule.y2mate(youtubeUrl, format, isVideo ? '360p' : '128kbps');
        if (res && res.status && res.url) {
            return { dlUrl: res.url, title: res.title || "YouTube Track" };
        }
    } catch (e) {
        console.log("⚠️ Y2Mate Engine Failed, trying YTMP3 fallback...");
    }

    // 2. Secondary Scraper: YTMP3 / Akuari
    try {
        const ytmp3Module = require('./ytmp3.js');
        const res = await ytmp3Module.ytdl(youtubeUrl, format);
        if (res && res.status && res.dl) {
            return { dlUrl: res.dl, title: res.title || "YouTube Track" };
        }
    } catch (e) {
        console.log("⚠️ YTMP3 Engine Failed...");
    }

    throw new Error("Unable to extract download link from available scrapers.");
}

async function resolveTrack(query, isVideo = false) {
    let videoId = "";
    let youtubeUrl = "";
    let searchMetadata = {};

    if (query.match(/(?:youtube\.com|youtu\.be)/i)) {
        youtubeUrl = query;
        const match = query.match(/(?:v=|\/)([a-zA-Z0-9_-]{11})/);
        videoId = match ? match[1] : Date.now().toString();
    } else {
        const searchResult = await yts(query);
        if (!searchResult.videos || searchResult.videos.length === 0) {
            throw new Error("No songs found on YouTube.");
        }
        const topResult = searchResult.videos[0];
        videoId = topResult.videoId;
        youtubeUrl = topResult.url;
        searchMetadata = {
            title: topResult.title,
            artist: topResult.author.name,
            duration: topResult.seconds,
            thumbnail: topResult.thumbnail
        };
    }

    // Check Cache
    const cached = db.getSong(videoId);
    if (cached && fs.existsSync(cached.local_path)) {
        return {
            id: cached.id,
            title: cached.title,
            artist: cached.artist,
            duration: cached.duration,
            thumbnail: cached.thumbnail,
            localPath: cached.local_path,
            telegramFileId: cached.telegram_file_id,
            isVideo: isVideo
        };
    }

    // Download from Scraper
    const { dlUrl, title } = await fetchDownloadUrl(youtubeUrl, isVideo);
    const ext = isVideo ? "mp4" : "mp3";
    const localPath = path.join(config.cacheDir, `${videoId}.${ext}`);

    const response = await axios({
        method: 'get',
        url: dlUrl,
        responseType: 'stream'
    });

    const writer = fs.createWriteStream(localPath);
    response.data.pipe(writer);

    return new Promise((resolve, reject) => {
        writer.on('finish', () => {
            const songData = {
                id: videoId,
                title: searchMetadata.title || title,
                artist: searchMetadata.artist || "YouTube Artist",
                duration: searchMetadata.duration || 180,
                thumbnail: searchMetadata.thumbnail || "",
                localPath: localPath,
                telegramFileId: null
            };
            db.saveSong(songData);
            resolve({ ...songData, isVideo });
        });

        writer.on('error', (err) => {
            reject(err);
        });
    });
}

module.exports = { resolveTrack };
