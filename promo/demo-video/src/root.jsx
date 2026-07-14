import React from 'react';
import {Composition} from 'remotion';
import {StockAnalysisDemo} from './video';

export const Root = () => (
  <>
    <Composition
      id="StockAnalysisDemo"
      component={StockAnalysisDemo}
      durationInFrames={2160}
      fps={30}
      width={1920}
      height={1080}
      defaultProps={{language: 'en'}}
    />
    <Composition
      id="StockAnalysisDemoZh"
      component={StockAnalysisDemo}
      durationInFrames={2160}
      fps={30}
      width={1920}
      height={1080}
      defaultProps={{language: 'zh'}}
    />
  </>
);
