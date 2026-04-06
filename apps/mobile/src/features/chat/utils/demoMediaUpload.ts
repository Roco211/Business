import * as Crypto from "expo-crypto";

type CreateMediaUploadInput = {
  media_type: string;
  file_name: string;
  content_type: string;
  size_bytes: number;
};

type CreateMediaUploadResult = {
  data: {
    media_id: string;
    upload_url: string;
  };
};

type CompleteMediaUploadInput = {
  checksum_sha256: string;
  size_bytes: number;
};

type CompleteMediaUploadResult = {
  data: {
    media_id: string;
    status: string;
  };
};

type UploadDemoMediaInput = {
  mediaType: string;
  fileName: string;
  contentType: string;
  body: string;
  createMediaUpload: (input: CreateMediaUploadInput) => Promise<CreateMediaUploadResult | null>;
  completeMediaUpload: (
    mediaId: string,
    input: CompleteMediaUploadInput,
  ) => Promise<CompleteMediaUploadResult | null>;
  onUploadError?: (message: string) => void;
};

function getBodySizeBytes(body: string) {
  if (typeof TextEncoder !== "undefined") {
    return new TextEncoder().encode(body).byteLength;
  }

  let sizeBytes = 0;
  for (const character of body) {
    const codePoint = character.codePointAt(0) ?? 0;
    if (codePoint <= 0x7f) {
      sizeBytes += 1;
      continue;
    }
    if (codePoint <= 0x7ff) {
      sizeBytes += 2;
      continue;
    }
    if (codePoint <= 0xffff) {
      sizeBytes += 3;
      continue;
    }
    sizeBytes += 4;
  }
  return sizeBytes;
}

export async function uploadDemoMedia(input: UploadDemoMediaInput): Promise<string | null> {
  try {
    const sizeBytes = getBodySizeBytes(input.body);
    const createdUpload = await input.createMediaUpload({
      media_type: input.mediaType,
      file_name: input.fileName,
      content_type: input.contentType,
      size_bytes: sizeBytes,
    });
    if (createdUpload === null) {
      return null;
    }

    const uploadResponse = await fetch(createdUpload.data.upload_url, {
      method: "PUT",
      headers: {
        "Content-Type": input.contentType,
      },
      body: input.body,
    });
    if (!uploadResponse.ok) {
      throw new Error("Failed to upload demo media bytes");
    }

    const checksumSha256 = await Crypto.digestStringAsync(
      Crypto.CryptoDigestAlgorithm.SHA256,
      input.body,
      { encoding: Crypto.CryptoEncoding.HEX },
    );
    const completedUpload = await input.completeMediaUpload(createdUpload.data.media_id, {
      checksum_sha256: checksumSha256,
      size_bytes: sizeBytes,
    });
    if (completedUpload === null) {
      return null;
    }

    return completedUpload.data.media_id;
  } catch (reason: unknown) {
    const message = reason instanceof Error ? reason.message : "Failed to upload demo media bytes";
    input.onUploadError?.(message);
    return null;
  }
}
