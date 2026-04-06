jest.mock("expo-crypto", () => ({
  CryptoDigestAlgorithm: {
    SHA256: "SHA256",
  },
  CryptoEncoding: {
    HEX: "hex",
  },
  digestStringAsync: jest.fn(async (_algorithm: string, input: string) =>
    require("crypto").createHash("sha256").update(input, "utf8").digest("hex"),
  ),
}));

import { uploadDemoMedia } from "../src/features/chat/utils/demoMediaUpload";

describe("uploadDemoMedia", () => {
  afterEach(() => {
    jest.resetAllMocks();
  });

  it("creates upload, uploads bytes via PUT, completes upload, and returns media id", async () => {
    const body = "receipt demo content";
    const expectedSize = new TextEncoder().encode(body).byteLength;
    const expectedChecksum = require("crypto").createHash("sha256").update(body, "utf8").digest("hex");
    const createMediaUpload = jest.fn().mockResolvedValue({
      data: {
        media_id: "media_receipt_1",
        upload_url: "https://mock.example/uploads/media_receipt_1",
      },
    });
    const completeMediaUpload = jest.fn().mockResolvedValue({
      data: {
        media_id: "media_receipt_1",
        status: "uploaded",
      },
    });
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
    }) as unknown as typeof fetch;

    const mediaId = await uploadDemoMedia({
      mediaType: "receipt-image",
      fileName: "receipt-demo.jpg",
      contentType: "image/jpeg",
      body,
      createMediaUpload,
      completeMediaUpload,
    });

    expect(mediaId).toBe("media_receipt_1");
    expect(createMediaUpload).toHaveBeenCalledWith({
      media_type: "receipt-image",
      file_name: "receipt-demo.jpg",
      content_type: "image/jpeg",
      size_bytes: expectedSize,
    });
    expect(global.fetch).toHaveBeenCalledWith("https://mock.example/uploads/media_receipt_1", {
      method: "PUT",
      headers: {
        "Content-Type": "image/jpeg",
      },
      body,
    });
    expect(completeMediaUpload).toHaveBeenCalledWith("media_receipt_1", {
      checksum_sha256: expectedChecksum,
      size_bytes: expectedSize,
    });
  });

  it("returns null without upload call when create upload fails", async () => {
    const createMediaUpload = jest.fn().mockResolvedValue(null);
    const completeMediaUpload = jest.fn();
    global.fetch = jest.fn() as unknown as typeof fetch;

    const mediaId = await uploadDemoMedia({
      mediaType: "audio",
      fileName: "voice-demo.m4a",
      contentType: "audio/m4a",
      body: "restock apples today",
      createMediaUpload,
      completeMediaUpload,
    });

    expect(mediaId).toBeNull();
    expect(global.fetch).not.toHaveBeenCalled();
    expect(completeMediaUpload).not.toHaveBeenCalled();
  });

  it("returns null and reports a recoverable error when PUT upload fails", async () => {
    const createMediaUpload = jest.fn().mockResolvedValue({
      data: {
        media_id: "media_voice_1",
        upload_url: "https://mock.example/uploads/media_voice_1",
      },
    });
    const completeMediaUpload = jest.fn();
    const onUploadError = jest.fn();
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
    }) as unknown as typeof fetch;

    const mediaId = await uploadDemoMedia({
      mediaType: "audio",
      fileName: "voice-demo.m4a",
      contentType: "audio/m4a",
      body: "stock out cola for walk in sale",
      createMediaUpload,
      completeMediaUpload,
      onUploadError,
    });

    expect(mediaId).toBeNull();
    expect(onUploadError).toHaveBeenCalledWith("Failed to upload demo media bytes");
    expect(completeMediaUpload).not.toHaveBeenCalled();
  });

  it("returns null when complete upload fails", async () => {
    const createMediaUpload = jest.fn().mockResolvedValue({
      data: {
        media_id: "media_image_1",
        upload_url: "https://mock.example/uploads/media_image_1",
      },
    });
    const completeMediaUpload = jest.fn().mockResolvedValue(null);
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
    }) as unknown as typeof fetch;

    const mediaId = await uploadDemoMedia({
      mediaType: "image",
      fileName: "photo-demo.jpg",
      contentType: "image/jpeg",
      body: "check shelf stock for red bull",
      createMediaUpload,
      completeMediaUpload,
    });

    expect(mediaId).toBeNull();
  });
});
