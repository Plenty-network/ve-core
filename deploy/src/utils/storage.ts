interface PlyStorageParams {
  admin: string;
}

export const getPlyStorage = (params: PlyStorageParams): string => {
  return `(Pair (Pair "${params.admin}" (Pair {} {Elt "" 0x697066733a2f2f516d6479777a77736e357072654e6e61386950526738503867337251577a724c58686e726b4a655374765a745568})) (Pair {} (Pair {Elt 0 (Pair 0 {Elt "decimals" 0x3138; Elt "name" 0x506c656e747920504c59; Elt "symbol" 0x504c59; Elt "thumbnailUri" 0x697066733a2f2f516d517332585a4c46737a71356e706b596474336f4454617a77315878704759484a574c386f334c54477a566b55})} 0)))`;
};

interface VEStorageParams {
  baseToken: string;
}

export const getVEStorage = (params: VEStorageParams): string => {
  return `(Pair (Pair (Pair (Pair {} "${params.baseToken}") (Pair {} {})) (Pair (Pair 0 {}) (Pair {} 0))) (Pair (Pair (Pair {} {Elt "" 0x697066733a2f2f516d586e5373396e6a51744545617565764179687735764b7145696e466d6965715842774878504b76584d4b4441}) (Pair {} {})) (Pair (Pair {} {}) (Pair 0 "tz1RBkXZSiQb3fS7Sg3zbFdPMBFPJUNHdcFo"))))`;
};

interface VoterStorageParams {
  plyAddress: string;
  veAddress: string;
}

export const getVoterStorage = (params: VoterStorageParams): string => {
  return `(Pair (Pair (Pair {} (Pair "KT1TezoooozzSmartPyzzDYNAMiCzzpLu4LU" (Pair 2000000000000000000000000 (Pair 0 0)))) (Pair 0 (Pair {} "KT1TezoooozzSmartPyzzDYNAMiCzzpLu4LU"))) (Pair (Pair "${params.plyAddress}" (Pair {} {})) (Pair {} (Pair {} "${params.veAddress}"))))`;
};

interface FactoryStorageParams {
  admin: string;
  plyAddress: string;
  veAddress: string;
  voterAddress: string;
}

export const getFactoryStorage = (params: FactoryStorageParams): string => {
  return `(Pair (Pair (Pair "${params.admin}" {}) (Pair "tz1RBkXZSiQb3fS7Sg3zbFdPMBFPJUNHdcFo" "${params.plyAddress}")) (Pair (Pair None None) (Pair "${params.admin}" (Pair "${params.veAddress}" "${params.voterAddress}"))))`;
};

interface FeeDistributorStorageParams {
  factoryAddress: string;
  voterAddress: string;
}

export const getFeeDistributorStorage = (params: FeeDistributorStorageParams): string => {
  return `(Pair (Pair {} {}) (Pair {} (Pair "${params.factoryAddress}" "${params.voterAddress}")))`;
};

interface VESwapStorageParams {
  plyAddress: string;
  plentyAddress: string;
  wrapAddress: string;
  veSwapGenesis: string;
  veSwapEnd: string;
  plentyExchangeVal: string;
  wrapExchangeVal: string;
}

export const getVESwapStorage = (params: VESwapStorageParams): string => {
  return `(Pair (Pair (Pair "${params.veSwapEnd}" "${params.veSwapGenesis}") (Pair {} "${params.plentyAddress}")) (Pair (Pair ${params.plentyExchangeVal} "${params.plyAddress}") (Pair "${params.wrapAddress}" ${params.wrapExchangeVal})))`;
};
