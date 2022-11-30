interface PlyStorageParams {
  admin: string;
}

export const getPlyStorage = (params: PlyStorageParams): string => {
  return `(Pair (Pair "${params.admin}" (Pair {} {Elt "" 0x697066733a2f2f516d6479777a77736e357072654e6e61386950526738503867337251577a724c58686e726b4a655374765a745568})) (Pair {} (Pair {Elt 0 (Pair 0 {Elt "decimals" 0x3138; Elt "icon" 0x697066733a2f2f516d52775038554a5571516632753554747834626457756869686b634774526f4a6f41656b71396a364137684a4d; Elt "name" 0x506c656e747920504c59; Elt "symbol" 0x504c59})} 0)))`;
};

interface VEStorageParams {
  baseToken: string;
}

export const getVEStorage = (params: VEStorageParams): string => {
  return `(Pair (Pair (Pair (Pair {} "${params.baseToken}") (Pair {} {})) (Pair (Pair 0 {}) (Pair {} 0))) (Pair (Pair (Pair {} {Elt "" 0x697066733a2f2f516d56334b696831577139457948546945664a6e5479786472717232466935396a4c4d7669634643796836427362}) (Pair {} {})) (Pair (Pair {} {}) (Pair 0 "tz1RBkXZSiQb3fS7Sg3zbFdPMBFPJUNHdcFo"))))`;
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
  plentyExchangeVal: number;
  wrapExchangeVal: string;
}

export const getVESwapStorage = (params: VESwapStorageParams): string => {
  return `(Pair (Pair (Pair "${params.veSwapEnd}" "${params.veSwapGenesis}") (Pair {} "${params.plentyAddress}")) (Pair (Pair ${params.plentyExchangeVal} "${params.plyAddress}") (Pair "${params.wrapAddress}" ${params.wrapExchangeVal})))`;
};
