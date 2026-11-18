/**
 * Persistent Web Audio graph with singleton node reuse per D-05.
 *
 * Browsers forbid calling createMediaElementSource() more than once on the same
 * HTMLMediaElement, throwing uncatchable InvalidStateError. This module holds a
 * persistent singleton AudioContext, MediaElementAudioSourceNode, GainNode, and
 * MediaStreamDestination to route audio concurrently to user speakers and
 * MediaRecorder capture streams.
 */

let sharedAudioCtx: AudioContext | null = null;
let sharedSourceNode: MediaElementAudioSourceNode | null = null;
let sharedGainNode: GainNode | null = null;
let sharedStreamDest: MediaStreamAudioDestinationNode | null = null;
let attachedVideoEl: HTMLVideoElement | null = null;

export interface AudioGraphHandles {
  audioContext: AudioContext;
  sourceNode: MediaElementAudioSourceNode;
  gainNode: GainNode;
  streamDestination: MediaStreamAudioDestinationNode;
}

/**
 * Retrieve or create persistent Web Audio graph for the given HTMLVideoElement per D-05.
 */
export function getOrCreateAudioGraph(videoEl: HTMLVideoElement): AudioGraphHandles {
  if (!sharedAudioCtx || sharedAudioCtx.state === 'closed') {
    const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    sharedAudioCtx = new AudioContextClass();
    sharedSourceNode = null;
    sharedGainNode = null;
    sharedStreamDest = null;
    attachedVideoEl = null;
  }

  if (!sharedGainNode) {
    sharedGainNode = sharedAudioCtx.createGain();
    sharedGainNode.gain.value = 1.0;
  }

  if (!sharedStreamDest) {
    sharedStreamDest = sharedAudioCtx.createMediaStreamDestination();
  }

  // Create MediaElementAudioSourceNode once per element
  if (!sharedSourceNode || attachedVideoEl !== videoEl) {
    if (attachedVideoEl && attachedVideoEl !== videoEl) {
      console.warn('[AudioGraph] Video element changed; reusing AudioContext for new element.');
    }
    sharedSourceNode = sharedAudioCtx.createMediaElementSource(videoEl);
    attachedVideoEl = videoEl;

    // Dual routing per D-05:
    // 1. To speakers so user hears video playback during export
    sharedSourceNode.connect(sharedGainNode);
    sharedGainNode.connect(sharedAudioCtx.destination);

    // 2. To stream destination for MediaRecorder canvas track recording
    sharedGainNode.connect(sharedStreamDest);
  }

  return {
    audioContext: sharedAudioCtx,
    sourceNode: sharedSourceNode,
    gainNode: sharedGainNode,
    streamDestination: sharedStreamDest,
  };
}

/**
 * Resume AudioContext inside a user click interaction for browser autoplay compliance per D-05.
 */
export async function resumeAudioContext(): Promise<void> {
  if (sharedAudioCtx && sharedAudioCtx.state === 'suspended') {
    try {
      await sharedAudioCtx.resume();
    } catch (err) {
      console.warn('[AudioGraph] Failed to resume AudioContext:', err);
    }
  }
}

/**
 * Retrieve current audio stream track for muxing into canvas captureStream.
 */
export function getAudioStreamTrack(): MediaStreamTrack | null {
  if (sharedStreamDest && sharedStreamDest.stream) {
    const tracks = sharedStreamDest.stream.getAudioTracks();
    return tracks.length > 0 ? tracks[0] : null;
  }
  return null;
}
